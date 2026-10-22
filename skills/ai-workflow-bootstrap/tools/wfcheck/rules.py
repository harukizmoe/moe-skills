"""Workflow gates: the machine-checkable half of the pipeline.

A handoff is a *claim*. These rules decide whether the repository can confirm
it. They are deliberately mechanical: every rule either compares a stored value
against git or against another artifact, so a wrong or stale claim fails.

Invariant that carries most of the weight: evidence records the content hash of
the tree it ran against, so a test run cannot be reused for code that changed
afterwards.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from .gitinfo import (
    STATE_CONFIG,
    UNBORN,
    GitError,
    change_base,
    commit_exists,
    commit_tree,
    diff_size,
    head_sha,
    is_ancestor,
    only_state_between,
    status_lines,
)
from .model import Evidence, Handoff, Review, SchemaError, read_json

# A task's state is derived from its artifacts, never stored: a stored status is
# a value an agent can write, and a value an agent can write is not evidence.
# See task_state() for the derivation.
REQUIRED_EVIDENCE = ("test", "check")
# A change of at most this many lines needs no reviewer: the evidence re-run is
# already an independent check, and a review round costs minutes to tens of
# minutes. Over it, a reviewer must name the commit. The number is a project
# decision, so `.ai-workflow/config.sh` supplies it; this is the default.
DEFAULT_REVIEW_THRESHOLD = 400


@dataclass(frozen=True)
class Problem:
    code: str
    detail: str

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


@dataclass
class Report:
    task_id: str
    problems: list[Problem]
    facts: dict[str, str]

    @property
    def ok(self) -> bool:
        return not self.problems

    def lines(self) -> list[str]:
        out = [f"task {self.task_id}"]
        for key, value in self.facts.items():
            out.append(f"  {key:<16} {value}")
        if self.problems:
            out.append("  problems")
            out.extend(f"    - {p}" for p in self.problems)
        else:
            out.append("  verdict          PASS")
        return out


class Workspace:
    """Everything the rules read, resolved from a repository root."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.flow = root / ".ai-workflow"
        self.review_threshold = _review_threshold(root)

    def path(self, *parts: str) -> Path:
        return self.flow.joinpath(*parts)

    def tasks(self) -> dict[str, dict]:
        data = read_json(self.path("tasks", "tasks.json"))
        raw = data.get("tasks")
        if not isinstance(raw, list):
            raise SchemaError(".ai-workflow/tasks/tasks.json: 'tasks' must be a list")
        out: dict[str, dict] = {}
        for item in raw:
            if not isinstance(item, dict):
                raise SchemaError("tasks.json: each task must be an object")
            task_id = item.get("id")
            if not isinstance(task_id, str) or not task_id:
                raise SchemaError("tasks.json: each task needs a string 'id'")
            if task_id in out:
                raise SchemaError(f"tasks.json: duplicate task id '{task_id}'")
            if "status" in item:
                raise SchemaError(
                    f"tasks.json: task '{task_id}' still has a 'status'; it is derived now, "
                    "remove the field"
                )
            depends = item.get("depends_on", [])
            if not isinstance(depends, list) or any(not isinstance(d, str) for d in depends):
                raise SchemaError(f"tasks.json: task '{task_id}' depends_on must list ids")
            out[task_id] = item
        for task_id, item in out.items():
            for dep in item.get("depends_on", []):
                if dep not in out:
                    raise SchemaError(f"tasks.json: task '{task_id}' depends on unknown '{dep}'")
                if dep == task_id:
                    raise SchemaError(f"tasks.json: task '{task_id}' depends on itself")
        _reject_cycles(out)
        return out

    def handoff(self, task_id: str) -> Handoff:
        return Handoff.load(self.path("handoffs", f"{task_id}.json"))

    def evidence(self, handoff: Handoff) -> list[Evidence]:
        out = []
        for rel in handoff.evidence:
            candidate = self._resolve(rel)
            out.append(Evidence.load(candidate))
        return out

    def review_paths(self, task_id: str) -> list[Path]:
        """Every review file for a task, valid or not, so callers can tell them apart."""
        folder = self.path("reviews")
        if not folder.is_dir():
            return []
        return sorted(folder.glob(f"{task_id}-r*.json"))

    def reviews(self, task_id: str) -> list[Review]:
        found = [Review.load(path) for path in self.review_paths(task_id)]
        found.sort(key=lambda r: r.round)
        return found

    def _resolve(self, rel: str) -> Path:
        """Evidence paths are repository-relative; absolute paths are refused."""
        candidate = Path(rel)
        if candidate.is_absolute():
            raise SchemaError(f"evidence path must be repository-relative: {rel}")
        return self.root / candidate


def _review_threshold(root: Path) -> int:
    """Lines a change may touch before it needs a reviewer, from .ai-workflow/config.sh.

    Read once per Workspace so every caller agrees: a threshold supplied per call
    is a second source of truth, and the one the gate happened to be given wins.
    """
    script = root / STATE_CONFIG
    if not script.is_file():
        return DEFAULT_REVIEW_THRESHOLD
    proc = subprocess.run(
        ["sh", "-c", f'. "{script}"\nprintf "%s" "${{WF_REVIEW_MAX:-}}"'],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    raw = proc.stdout.strip()
    return int(raw) if raw.isdigit() else DEFAULT_REVIEW_THRESHOLD


def _reject_cycles(tasks: dict[str, dict]) -> None:
    state: dict[str, int] = {}

    def visit(task_id: str, trail: tuple[str, ...]) -> None:
        mark = state.get(task_id, 0)
        if mark == 1:
            raise SchemaError(f"tasks.json: dependency cycle {' -> '.join((*trail, task_id))}")
        if mark == 2:
            return
        state[task_id] = 1
        for dep in tasks[task_id].get("depends_on", []):
            visit(dep, (*trail, task_id))
        state[task_id] = 2

    for task_id in tasks:
        visit(task_id, ())


def needs_review(ws: Workspace, handoff: Handoff) -> bool:
    """Whether this change is big enough to require a reviewer's verdict.

    The range comes from git (see `change_base`), so it works in a repository's
    first task as well as its hundredth, and it does not depend on how a task's
    commits happen to be split.
    """
    base = change_base(ws.root, handoff.commit_sha)
    return diff_size(ws.root, base, handoff.commit_sha) > ws.review_threshold


def task_state(ws: Workspace, task_id: str, tasks: dict[str, dict] | None = None) -> str:
    """A task's state, derived from its artifacts instead of stored.

    Four states, in the order they occur:

    * `todo`     - no handoff, so nobody has claimed the work yet;
    * `review`   - a handoff big enough to need a reviewer, at HEAD, unreviewed;
    * `revise`   - a handoff whose commit is behind HEAD, or whose latest review
                   asked for changes: the work needs another pass;
    * `merged`   - the approved commit is an ancestor of HEAD, or the change was
                   small enough that re-running its evidence was the whole check.

    Because nothing here is stored, there is nothing to forge: an agent cannot
    "mark a task done", it can only produce a handoff, a review, and a commit
    that the gate then reads back.

    The size threshold is the one place the workflow spends review effort in
    proportion to risk: re-running the evidence is already an independent check,
    so a small change does not also pay for a human-shaped round.
    """
    tasks = tasks or ws.tasks()
    if task_id not in tasks:
        raise SchemaError(f"no task '{task_id}' in tasks.json")
    handoff_path = ws.path("handoffs", f"{task_id}.json")
    if not handoff_path.is_file():
        return "todo"
    try:
        handoff = ws.handoff(task_id)
    except SchemaError:
        return "revise"
    head = head_sha(ws.root)
    on_head = head == handoff.commit_sha
    try:
        latest = ws.reviews(task_id)[-1] if ws.reviews(task_id) else None
    except SchemaError:
        return "revise"
    if latest is not None and latest.verdict == "changes_requested":
        return "revise"
    reviewed = latest is not None and latest.verdict == "approved"
    try:
        big = needs_review(ws, handoff)
    except GitError:
        # A change whose size cannot be measured is treated as needing review.
        big = True
    if on_head:
        return "review" if big and not reviewed else "merged"
    if (reviewed or not big) and commit_exists(ws.root, handoff.commit_sha):
        if is_ancestor(ws.root, handoff.commit_sha, "HEAD"):
            return "merged"
    return "revise"


def gate(
    ws: Workspace,
    task_id: str,
    strict: bool = True,
    declared: dict[str, str] | None = None,
) -> Report:
    """Gate for one task: claim, evidence, review, and git must agree.

    Two callers, two questions:

    * `strict` (the default, used by `gate` and `verify` right before merging):
      may the current HEAD be merged? HEAD must be exactly the reviewed commit,
      or work nobody reviewed would ride along with it.
    * relaxed (used by `status` and `workspace`): is this task's approved work in
      the branch? Then the reviewed commit only has to be an ancestor of HEAD,
      because later commits belong to later tasks.

    Strictness is a parameter rather than a stored flag: a stored "already
    merged" bit is a value an agent could write, which is what this design
    removed.

    `declared` maps an evidence kind to the command the project's own
    configuration names for it. When supplied, a record naming any other command
    is refused: the record was not produced by this project's verification, so
    its exit code says nothing about this project. Callers that do not read the
    configuration omit it, and the check is skipped rather than guessed.
    """
    facts: dict[str, str] = {}
    problems: list[Problem] = []

    tasks = ws.tasks()
    if task_id not in tasks:
        problems.append(Problem("unknown-task", f"no task '{task_id}' in tasks.json"))
        return Report(task_id, problems, facts)
    item = tasks[task_id]
    state = task_state(ws, task_id, tasks)
    merged = state == "merged"
    facts["state"] = state

    for dep in item.get("depends_on", []):
        dep_state = task_state(ws, dep, tasks)
        facts[f"dep:{dep}"] = dep_state
        if dep_state != "merged":
            problems.append(
                Problem("dependency-open", f"dependency {dep} is {dep_state}, not merged")
            )

    try:
        handoff = ws.handoff(task_id)
    except SchemaError as exc:
        problems.append(Problem("handoff-missing", str(exc)))
        return Report(task_id, problems, facts)

    facts["claimed_sha"] = handoff.commit_sha[:12] or "(empty)"
    facts["claimed_tree"] = handoff.tree[:12] or "(empty)"

    head = head_sha(ws.root)
    facts["head"] = head[:12] if head != UNBORN else "(unborn)"

    if not commit_exists(ws.root, handoff.commit_sha):
        problems.append(
            Problem(
                "commit-unknown", f"commit {handoff.commit_sha or '(empty)'} is not in this repo"
            )
        )
    else:
        try:
            claimed_tree = commit_tree(ws.root, handoff.commit_sha)
        except GitError as exc:
            problems.append(Problem("commit-unreadable", str(exc)))
        else:
            facts["actual_tree"] = claimed_tree[:12]
            if claimed_tree != handoff.tree:
                problems.append(
                    Problem(
                        "tree-mismatch",
                        f"handoff claims tree {handoff.tree[:12]}, commit "
                        f"{handoff.commit_sha[:12]} is {claimed_tree[:12]}",
                    )
                )
        if not merged and not is_ancestor(ws.root, handoff.commit_sha, "HEAD"):
            problems.append(
                Problem(
                    "commit-not-merged", f"{handoff.commit_sha[:12]} is not an ancestor of HEAD"
                )
            )

    dirty = status_lines(ws.root)
    facts["dirty"] = str(len(dirty))
    # `merged` now also covers a small change still sitting on HEAD, so it cannot
    # exempt a dirty tree by itself: what makes dirt harmless is that the work is
    # already behind HEAD, and later edits belong to a later task.
    behind_head = head != UNBORN and handoff.commit_sha and head != handoff.commit_sha
    if dirty and not (merged and behind_head):
        problems.append(
            Problem(
                "worktree-dirty",
                f"{len(dirty)} uncommitted change(s); commit or stash before gating",
            )
        )

    evidence = _load_evidence(ws, handoff, problems, declared or {})
    kinds = {e.kind for e in evidence if e.exit_code == 0 and e.tree == handoff.tree}
    facts["evidence"] = ",".join(sorted(kinds)) or "(none)"
    for kind in REQUIRED_EVIDENCE:
        if kind not in kinds:
            problems.append(
                Problem(
                    "evidence-missing", f"no passing '{kind}' evidence for tree {handoff.tree[:12]}"
                )
            )
    reviews = _load_reviews(ws, task_id, problems)
    if reviews:
        latest = reviews[-1]
        facts["review"] = f"r{latest.round} {latest.verdict} @ {latest.reviewed_sha[:12]}"
        if latest.reviewed_sha != handoff.commit_sha:
            problems.append(
                Problem(
                    "review-stale",
                    f"latest review r{latest.round} covers {latest.reviewed_sha[:12]} "
                    f"but handoff claims {handoff.commit_sha[:12]}",
                )
            )
        if latest.verdict != "approved":
            problems.append(
                Problem("not-approved", f"latest review r{latest.round} is {latest.verdict}")
            )
        blockers = [f for f in latest.findings if f.severity == "blocker"]
        if blockers:
            problems.append(
                Problem(
                    "open-blockers",
                    f"r{latest.round} lists blockers: {', '.join(b.id for b in blockers)}",
                )
            )
        if latest.round != len(reviews):
            problems.append(
                Problem(
                    "review-sequence",
                    f"review rounds are not contiguous: have {[r.round for r in reviews]}",
                )
            )
    elif _needs_review_fact(ws, handoff, facts):
        problems.append(Problem("review-missing", f"no review for task {task_id}"))

    # Commits that only record state are bookkeeping, not work nobody reviewed:
    # recording a handoff moves HEAD past the commit the handoff names.
    if head == UNBORN or not handoff.commit_sha:
        head_moved = False
    else:
        head_moved = head != handoff.commit_sha and not only_state_between(
            ws.root, handoff.commit_sha, head
        )
    if head_moved and (strict or not merged):
        problems.append(
            Problem(
                "head-advanced",
                f"HEAD {head[:12]} is not the reviewed commit {handoff.commit_sha[:12]}",
            )
        )

    return Report(task_id, problems, facts)


def _needs_review_fact(ws: Workspace, handoff: Handoff, facts: dict[str, str]) -> bool:
    """Record the change size and say whether a reviewer is required.

    The fact is printed either way, so a skipped review is visible rather than
    silent: the coordinator must be able to see that a small change merged on
    evidence alone.
    """
    try:
        base = change_base(ws.root, handoff.commit_sha)
        size = diff_size(ws.root, base, handoff.commit_sha)
    except GitError:
        facts["change_size"] = "unreadable, review required"
        return True
    threshold = ws.review_threshold
    needed = size > threshold
    facts["change_size"] = (
        f"{size} lines, review required over {threshold}"
        if needed
        else f"{size} lines, no review under {threshold}"
    )
    return needed


def _load_evidence(
    ws: Workspace,
    handoff: Handoff,
    problems: list[Problem],
    declared: dict[str, str],
) -> list[Evidence]:
    loaded: list[Evidence] = []
    for rel in handoff.evidence:
        try:
            evidence = Evidence.load(ws._resolve(rel))
        except SchemaError as exc:
            problems.append(Problem("evidence-invalid", str(exc)))
            continue
        loaded.append(evidence)
        if evidence.task_id != handoff.task_id:
            problems.append(
                Problem(
                    "evidence-task",
                    f"{rel} records task {evidence.task_id}, handoff is {handoff.task_id}",
                )
            )
        if evidence.exit_code != 0:
            problems.append(Problem("evidence-failed", f"{rel} exited {evidence.exit_code}"))
        expected = declared.get(evidence.kind)
        if expected is not None and evidence.command != expected:
            problems.append(
                Problem(
                    "evidence-command",
                    f"{rel} records '{evidence.command}', but the project declares '{expected}'",
                )
            )
        if evidence.tree != handoff.tree:
            problems.append(
                Problem(
                    "evidence-stale",
                    f"{rel} ran against tree {evidence.tree[:12]}, "
                    f"handoff claims {handoff.tree[:12]}",
                )
            )
    return loaded


def _load_reviews(ws: Workspace, task_id: str, problems: list[Problem]) -> list[Review]:
    try:
        return ws.reviews(task_id)
    except SchemaError as exc:
        problems.append(Problem("review-invalid", str(exc)))
        return []
