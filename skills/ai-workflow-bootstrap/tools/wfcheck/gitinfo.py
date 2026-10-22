"""Git facts the gates depend on.

Every helper is read-only with one deliberate exception: tree hashing stages into
a throwaway index file, so it can hash a working tree or a commit's tree without
touching the repository's own index, refs, or history.

`.ai-workflow` is excluded from every fingerprint. Workflow state is committed
for auditability, but recording state (evidence, handoffs, reviews) must not
change the hash that binds evidence to code — otherwise the act of recording a
result would invalidate the result.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

UNBORN = "0" * 40
# The empty tree: the honest start of a range for a repository's first task.
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
# Vendored tooling, not authored work. The installer puts these in place; counting
# them would make a project's first task look like a thousand-line change and
# demand a review for installing the kit.
VENDORED = ("tools/wfcheck", "scripts")
STATE_DIR = ".ai-workflow"


class GitError(RuntimeError):
    """A git invocation the caller needed failed."""


def _git(repo: Path, *args: str, env: dict[str, str] | None = None) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        env={**os.environ, **(env or {})},
    )
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip()
        raise GitError(f"git {' '.join(args)} failed: {detail}")
    return proc.stdout.decode("utf-8", "replace")


def repo_root(start: Path) -> Path:
    """Nearest ancestor that is a git work tree."""
    out = _git(start, "rev-parse", "--show-toplevel").strip()
    if not out:
        raise GitError(f"{start} is not inside a git work tree")
    return Path(out)


def head_sha(repo: Path) -> str:
    """Current HEAD commit, or UNBORN when the branch has no commit yet."""
    try:
        return _git(repo, "rev-parse", "--verify", "HEAD").strip()
    except GitError:
        return UNBORN


def commit_exists(repo: Path, sha: str) -> bool:
    if not sha:
        return False
    proc = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "-e", f"{sha}^{{commit}}"],
        check=False,
        capture_output=True,
    )
    return proc.returncode == 0


def is_ancestor(repo: Path, sha: str, ref: str = "HEAD") -> bool:
    proc = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", sha, ref],
        check=False,
        capture_output=True,
    )
    return proc.returncode == 0


def status_lines(repo: Path) -> list[str]:
    """Porcelain status for tracked work, excluding workflow state churn."""
    out = _git(repo, "status", "--porcelain=v1", "-uall", "--", ".")
    return [
        line
        for line in out.splitlines()
        if line.strip() and not line[3:].startswith(f"{STATE_DIR}/")
    ]


def worktree_tree(repo: Path) -> str:
    """Content hash of the working tree, independent of commits and HEAD.

    Stages every tracked and untracked (non-ignored) file into a temporary index
    and writes a tree object, so the same content yields the same id before and
    after it is committed.
    """
    scratch = Path(tempfile.mkdtemp(prefix="wfcheck-index-"))
    try:
        env = {"GIT_INDEX_FILE": str(scratch / "index")}
        _git(repo, "add", "-A", env=env)
        _git(repo, "rm", "-r", "-q", "--cached", "--ignore-unmatch", STATE_DIR, env=env)
        return _git(repo, "write-tree", env=env).strip()
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def touches_only_state(repo: Path, rev: str) -> bool:
    """True when a commit changed nothing outside `.ai-workflow/`.

    A root commit has no parent to diff against; it is never "state only", which
    keeps the walk from treating the first commit as bookkeeping.
    """
    try:
        out = _git(repo, "diff", "--name-only", f"{rev}^", rev)
    except GitError:
        return False
    files = [line for line in out.splitlines() if line.strip()]
    return bool(files) and all(f.startswith(STATE_DIR + "/") for f in files)


def only_state_between(repo: Path, base: str, rev: str) -> bool:
    """True when every commit in `base..rev` touched nothing but workflow state.

    Used to decide whether HEAD moved past the handoff in any meaningful way: a
    handoff commit, and any commit after it that only records state, is
    bookkeeping rather than unreviewed work.
    """
    if base == rev:
        return True
    try:
        out = _git(repo, "rev-list", f"{base}..{rev}")
    except GitError:
        return False
    commits = [line for line in out.splitlines() if line.strip()]
    if not commits:
        return False
    return all(touches_only_state(repo, sha) for sha in commits)


def code_head(repo: Path, rev: str = "HEAD") -> str:
    """`rev` with any trailing commits that touched only workflow state removed.

    Recording a handoff commits `.ai-workflow/`, which would otherwise make HEAD
    differ from the handoff's own commit and read as "work landed after review".
    State commits carry no code, so they are not what that check is about.
    """
    current = rev
    while True:
        try:
            if not touches_only_state(repo, current):
                return current
        except GitError:
            return current
        ancestors = parents(repo, current)
        if not ancestors:
            return current
        current = ancestors[0]


def change_base(repo: Path, rev: str) -> str:
    """The commit a task's change starts from, for a handoff naming `rev`.

    A task's evidence and handoff are usually committed after the code, so the
    handoff commit can touch nothing but `.ai-workflow/`. Walking back over that
    trailing run finds the commit that carried the actual work; the range then
    starts at its parent. Measuring `rev` alone would report zero lines and skip
    review for a large change.
    """
    current = rev
    while True:
        try:
            if not touches_only_state(repo, current):
                break
        except GitError:
            break
        ancestors = parents(repo, current)
        if not ancestors:
            break
        current = ancestors[0]
    head_parents = parents(repo, current)
    return head_parents[0] if head_parents else EMPTY_TREE


def commit_tree(repo: Path, rev: str) -> str:
    """Content hash of a commit's tree, excluding workflow state.

    Uses the same exclusion as `worktree_tree`, so a handoff's claimed hash can
    be compared against a commit and against the working tree identically.
    """
    scratch = Path(tempfile.mkdtemp(prefix="wfcheck-commit-"))
    try:
        env = {"GIT_INDEX_FILE": str(scratch / "index")}
        _git(repo, "read-tree", rev, env=env)
        # `-f` is required: git refuses to unstage a path whose staged content
        # matches neither HEAD nor the working tree, which is the normal case
        # once workflow state has been committed and then edited.
        _git(
            repo,
            "rm",
            "-r",
            "-f",
            "-q",
            "--cached",
            "--ignore-unmatch",
            STATE_DIR,
            env=env,
        )
        return _git(repo, "write-tree", env=env).strip()
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def parents(repo: Path, rev: str) -> list[str]:
    """Parent shas of one commit, in git's order."""
    out = _git(repo, "rev-list", "--parents", "-n", "1", rev).split()
    return out[1:]


def diff_size(repo: Path, base: str, rev: str = "HEAD") -> int:
    """Lines added or removed between `base` and `rev`, excluding workflow state.

    Measured over a range, not a single commit: a task's work and its evidence can
    land in separate commits, and a handoff commit that only touches state would
    otherwise measure zero lines and skip review entirely.

    Size is what decides how much review a change needs, so it is read from git
    rather than written into an artifact: a declared "this is small" is exactly
    the kind of value an agent can lie about.
    """
    excludes = [f":(exclude){STATE_DIR}"]
    excludes += [f":(exclude){path}" for path in VENDORED]
    out = _git(repo, "diff", "--numstat", base, rev, "--", ".", *excludes)
    total = 0
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        added, removed = parts[0], parts[1]
        # Binary files report "-": they still changed, so count them as one.
        total += 1 if added == "-" else int(added) + int(removed)
    return total
