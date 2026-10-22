"""Command line surface for the workflow gates.

Two different jobs live here on purpose:

* `evidence` / `handoff` / `review` *write* artifacts, and they compute the git
  facts (commit sha, tree hash) and run the commands themselves, so an agent
  never supplies either by hand.
* `gate` / `status` / `workspace` / `ready` only read and refuse.

`gate` is the anti-forgery layer: after the artifacts agree, it re-runs every
command the handoff's evidence names and requires the tree to be unchanged, so a
hand-written verification record cannot survive it.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from . import gitinfo
from .model import EVIDENCE_KINDS, Review, SchemaError
from .rules import (
    REQUIRED_EVIDENCE,
    Workspace,
    gate,
    task_state,
)


def _fail(message: str) -> None:
    """Report a refusal on stdout so callers read one stream, then exit 1."""
    print(f"FAIL: {message}")
    raise SystemExit(1)


def _report_failure(exc: Exception) -> int:
    """One line on stdout, exit 1: an agent reads a stream, not a traceback.

    Git's own messages span several lines (and may be localized); collapsing
    whitespace keeps the contract `FAIL: <one line>` intact.
    """
    print(f"FAIL: {' '.join(str(exc).split())}")
    return 1


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _root(args: argparse.Namespace) -> Path:
    return Path(args.root or os.getcwd()).resolve()


def _task_id(args: argparse.Namespace) -> str:
    tasks = Workspace(_root(args)).tasks()
    if args.task not in tasks:
        _fail(f"unknown task '{args.task}'; known: {', '.join(sorted(tasks))}")
    return args.task


def configured_command(root: Path, kind: str) -> str:
    """The command this project declares for a kind, read from scripts/config.sh.

    The gate must never take a command from its caller: whoever writes the
    command decides what "verified" means, and a caller is exactly the party
    being checked. The project's own configuration is the only authority, so the
    configuration file itself. It does not read the environment, so `WF_TEST=true`
    cannot be a one-line bypass of the whole gate.
    """
    script = root / "scripts" / "config.sh"
    if not script.is_file():
        _fail(f"no scripts/config.sh in {root}; run scripts/install.sh first")
    probe = (
        # wf_python first: config.sh interpolates it into the command values.
        f'wf_python=${{WF_PYTHON:-python3}}\n. "{script}"\nwf_command {kind} "$WF_{kind.upper()}"\n'
    )
    proc = subprocess.run(
        ["sh", "-c", probe],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    command = proc.stdout.strip()
    if not command:
        _fail(f"no command configured for '{kind}' in scripts/config.sh")
    return command


def cmd_evidence(args: argparse.Namespace) -> int:
    """Run a project's declared command and record what actually happened.

    The command and the exit code are produced here, never supplied: this is the
    difference between a record and a claim.
    """
    root = _root(args)
    # Without --task this is a plain run: the developer gets the output and
    # nothing is recorded, so a mid-work check cannot become a claim.
    task_id = _task_id(args) if args.task else ""
    command = configured_command(root, args.kind)

    tree = gitinfo.worktree_tree(root)
    print(f"== {args.kind}: {command}")
    proc = subprocess.run(
        ["sh", "-c", command],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.stdout:
        sys.stdout.write(proc.stdout)
    if proc.stderr:
        sys.stderr.write(proc.stderr)

    after = gitinfo.worktree_tree(root)
    if after != tree:
        _fail(
            f"'{command}' changed the working tree ({tree[:12]} -> {after[:12]}); "
            "a verification command must not leave artifacts behind"
        )

    if task_id:
        payload = {
            "task_id": task_id,
            "kind": args.kind,
            "exit_code": proc.returncode,
            "command": command,
            "tree": tree,
            "recorded_at": _now(),
        }
        target = root / ".ai-workflow" / "evidence" / f"{task_id}-{args.kind}.json"
        _write(target, payload)
        print(f"evidence {target.relative_to(root)} tree={tree[:12]} exit={proc.returncode}")
    return 0 if proc.returncode == 0 else 1


def cmd_handoff(args: argparse.Namespace) -> int:
    root = _root(args)
    task_id = _task_id(args)
    head = gitinfo.head_sha(root)
    if head == gitinfo.UNBORN:
        _fail("cannot record a handoff: repository has no commit yet")
    tree = gitinfo.worktree_tree(root)
    for rel in args.evidence:
        path = root / rel
        if not path.is_file():
            _fail(f"evidence file does not exist: {rel}")
        recorded = json.loads(path.read_text(encoding="utf-8"))
        if recorded.get("tree") != tree:
            _fail(
                f"{rel} was recorded against tree {str(recorded.get('tree'))[:12]}, "
                f"working tree is {tree[:12]}; re-run the evidence commands"
            )
    payload = {
        "task_id": task_id,
        "commit_sha": head,
        "tree": tree,
        "evidence": list(args.evidence),
        "recorded_at": _now(),
    }
    target = root / ".ai-workflow" / "handoffs" / f"{task_id}.json"
    _write(target, payload)
    print(f"handoff {target.relative_to(root)} sha={head[:12]} tree={tree[:12]}")
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    root = _root(args)
    task_id = _task_id(args)
    ws = Workspace(root)
    existing = ws.reviews(task_id)
    rounds = [r.round for r in existing]
    expected = (max(rounds) if rounds else 0) + 1
    findings = []
    for spec in args.finding:
        parts = spec.split(":", 2)
        if len(parts) != 3:
            _fail(f"finding must be severity:id:summary, got {spec!r}")
        findings.append({"severity": parts[0], "id": parts[1], "summary": parts[2]})
    if args.verdict == "approved" and any(f["severity"] == "blocker" for f in findings):
        _fail("an approved review cannot carry blocker findings")
    if args.verdict == "changes_requested" and not findings:
        _fail("changes_requested needs at least one finding")
    head = gitinfo.head_sha(root)
    reviewed = args.reviewed_sha or head
    if not gitinfo.commit_exists(root, reviewed):
        _fail(f"reviewed commit {reviewed} is not in this repository")
    payload = {
        "task_id": task_id,
        "round": expected,
        "reviewed_sha": reviewed,
        "verdict": args.verdict,
        "findings": findings,
        "reviewed_at": _now(),
    }
    target = root / ".ai-workflow" / "reviews" / f"{task_id}-r{expected}.json"
    _write(target, payload)
    print(f"review r{expected} {args.verdict} sha={reviewed[:12]} findings={len(findings)}")
    return 0


def cmd_ready(args: argparse.Namespace) -> int:
    ws = Workspace(_root(args))
    tasks = ws.tasks()
    ready = [
        task_id
        for task_id, item in tasks.items()
        if task_state(ws, task_id, tasks) == "todo"
        and all(task_state(ws, dep, tasks) == "merged" for dep in item.get("depends_on", []))
    ]
    print("\n".join(ready) if ready else "(nothing ready)")
    return 0


def _latest_review(ws: Workspace, task_id: str) -> Review | None:
    reviews = ws.reviews(task_id)
    return reviews[-1] if reviews else None


def _review_label(row: dict) -> str:
    review = row["review"]
    return f"r{review.round} {review.verdict}" if review else "(no review)"


def _status_rows(ws: Workspace) -> list[dict]:
    """One row per task: state, latest review, and the gate's verdict.

    `gate` is what re-runs evidence; this only reads recorded artifacts.
    """
    rows: list[dict] = []
    tasks = ws.tasks()
    for task_id in tasks:
        rows.append(
            {
                "task_id": task_id,
                "state": task_state(ws, task_id, tasks),
                "review": _latest_review(ws, task_id),
                "gate_ok": gate(ws, task_id, strict=False).ok,
            }
        )
    return rows


def _status_lines(rows: list[dict]) -> list[str]:
    id_width = max((len(row["task_id"]) for row in rows), default=0)
    state_width = max((len(row["state"]) for row in rows), default=0)
    review_width = max((len(_review_label(row)) for row in rows), default=0)
    lines = []
    for row in rows:
        verdict = "PASS" if row["gate_ok"] else "FAIL"
        lines.append(
            f"{row['task_id']:<{id_width}}  {row['state']:<{state_width}}  "
            f"{_review_label(row):<{review_width}}  gate {verdict}"
        )
    return lines


def cmd_status(args: argparse.Namespace) -> int:
    """Every task's derived state, latest review, and whether the gate would pass."""
    rows = _status_rows(Workspace(_root(args)))
    if rows:
        print("\n".join(_status_lines(rows)))
    else:
        print("(no tasks)")
    # Nothing to merge is not a failure: a workspace mid-task exits 0.
    return 0 if all(row["gate_ok"] for row in rows if row["state"] == "merged") else 1


def declared_commands(root: Path, kinds: Iterable[str]) -> dict[str, str]:
    """The commands this project declares for `kinds`, for the gate to compare against."""
    return {kind: configured_command(root, kind) for kind in kinds}


def cmd_gate(args: argparse.Namespace) -> int:
    """Gate one task: compare the artifacts against git, then re-run the evidence.

    Re-running is not optional. A gate that can be asked to trust the record is a
    gate that reports what the record says, which is the failure mode this whole
    kit exists to prevent, so there is no flag to turn it off.
    """
    root = _root(args)
    ws = Workspace(root)
    try:
        report = gate(ws, args.task, declared=declared_commands(root, REQUIRED_EVIDENCE))
    except SchemaError as exc:
        print(f"gate {args.task} FAIL\n  - schema: {exc}")
        return 1
    print("\n".join(report.lines()))
    if not report.ok:
        return 1

    handoff = ws.handoff(args.task)
    evidence = ws.evidence(handoff)
    before = gitinfo.worktree_tree(root)
    for item in evidence:
        print(f"  rerun {item.kind:<10} {item.command}")
        proc = subprocess.run(
            ["sh", "-c", item.command],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            tail = "\n".join((proc.stdout + proc.stderr).strip().splitlines()[-25:])
            print(f"  rerun FAILED ({proc.returncode})\n{tail}")
            return 1
    after = gitinfo.worktree_tree(root)
    if after != before:
        print(f"  rerun mutated the tree: {before[:12]} -> {after[:12]}")
        return 1
    print(f"gate {args.task} PASS")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wfcheck", description="AI workflow gates")
    parser.add_argument("--root", help="repository root (default: cwd)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("evidence", help="run a project's declared command, recording it")
    p.add_argument("--task", help="task id; omit for a plain run that is not recorded")
    p.add_argument("--kind", required=True, choices=sorted(EVIDENCE_KINDS))
    p.set_defaults(func=cmd_evidence)

    p = sub.add_parser("handoff", help="record a developer handoff")
    p.add_argument("--task", required=True)
    p.add_argument("--evidence", nargs="+", default=[])
    p.set_defaults(func=cmd_handoff)

    p = sub.add_parser("review", help="record a reviewer verdict")
    p.add_argument("--task", required=True)
    p.add_argument("--verdict", required=True, choices=["approved", "changes_requested"])
    p.add_argument("--reviewed-sha", default="")
    p.add_argument("--finding", action="append", default=[], metavar="SEVERITY:ID:SUMMARY")
    p.set_defaults(func=cmd_review)

    p = sub.add_parser("ready", help="list tasks that can start now")
    p.set_defaults(func=cmd_ready)

    p = sub.add_parser("status", help="overview: every task's state, review, and gate")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("gate", help="gate one task, re-running its evidence")
    p.add_argument("--task", required=True)
    p.set_defaults(func=cmd_gate)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (SchemaError, gitinfo.GitError) as exc:
        return _report_failure(exc)


if __name__ == "__main__":
    sys.exit(main())
