"""Loading and shape-checking the workflow's JSON artifacts.

Shapes are validated strictly: a handoff or review with an unexpected type or a
missing required key is an error, not a silently ignored field. The whole point
of these files is that a gate can refuse them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

VERDICTS = {"approved", "changes_requested"}
SEVERITIES = {"blocker", "major", "minor"}
EVIDENCE_KINDS = {"test", "check", "smoke"}


class SchemaError(ValueError):
    """An artifact does not match its contract."""


def _require(obj: dict[str, Any], key: str, kind: type | tuple[type, ...], where: str) -> Any:
    if key not in obj:
        raise SchemaError(f"{where}: missing required key '{key}'")
    value = obj[key]
    if kind is bool and not isinstance(value, bool):
        raise SchemaError(f"{where}: '{key}' must be a boolean")
    if not isinstance(value, kind):
        raise SchemaError(f"{where}: '{key}' must be {kind}, got {type(value).__name__}")
    return value


@dataclass(frozen=True)
class Evidence:
    path: Path
    task_id: str
    kind: str
    exit_code: int
    command: str
    tree: str

    @classmethod
    def load(cls, path: Path) -> Evidence:
        where = str(path)
        data = read_json(path, where)
        kind = _require(data, "kind", str, where)
        if kind not in EVIDENCE_KINDS:
            raise SchemaError(f"{where}: unknown evidence kind '{kind}'")
        return cls(
            path=path,
            task_id=_require(data, "task_id", str, where),
            kind=kind,
            exit_code=_require(data, "exit_code", int, where),
            command=_require(data, "command", str, where),
            tree=_require(data, "tree", str, where),
        )


@dataclass(frozen=True)
class Finding:
    id: str
    severity: str
    summary: str


@dataclass(frozen=True)
class Handoff:
    """A developer's claim: this commit, this tree, these evidence files.

    Nothing else. A handoff exists or it does not, so there is no status to
    check and no "tests passed" flag to argue with: the evidence for `test` is
    the claim about tests, and the gate re-runs it.
    """

    path: Path
    task_id: str
    commit_sha: str
    tree: str
    evidence: tuple[str, ...]

    @classmethod
    def load(cls, path: Path) -> Handoff:
        where = str(path)
        data = read_json(path, where)
        evidence = _require(data, "evidence", list, where)
        if any(not isinstance(item, str) for item in evidence):
            raise SchemaError(f"{where}: 'evidence' must list paths")
        return cls(
            path=path,
            task_id=_require(data, "task_id", str, where),
            commit_sha=_require(data, "commit_sha", str, where),
            tree=_require(data, "tree", str, where),
            evidence=tuple(evidence),
        )


@dataclass(frozen=True)
class Review:
    path: Path
    task_id: str
    round: int
    reviewed_sha: str
    verdict: str
    findings: tuple[Finding, ...] = field(default=())

    @classmethod
    def load(cls, path: Path) -> Review:
        where = str(path)
        data = read_json(path, where)
        verdict = _require(data, "verdict", str, where)
        if verdict not in VERDICTS:
            raise SchemaError(f"{where}: verdict must be one of {sorted(VERDICTS)}")
        raw = _require(data, "findings", list, where)
        findings = []
        for item in raw:
            if not isinstance(item, dict):
                raise SchemaError(f"{where}: each finding must be an object")
            severity = _require(item, "severity", str, f"{where}:finding")
            if severity not in SEVERITIES:
                raise SchemaError(f"{where}: unknown severity '{severity}'")
            findings.append(
                Finding(
                    id=_require(item, "id", str, f"{where}:finding"),
                    severity=severity,
                    summary=_require(item, "summary", str, f"{where}:finding"),
                )
            )
        return cls(
            path=path,
            task_id=_require(data, "task_id", str, where),
            round=_require(data, "round", int, where),
            reviewed_sha=_require(data, "reviewed_sha", str, where),
            verdict=verdict,
            findings=tuple(findings),
        )


def read_json(path: Path, where: str | None = None) -> dict[str, Any]:
    label = where or str(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SchemaError(f"{label}: file does not exist") from exc
    except json.JSONDecodeError as exc:
        raise SchemaError(f"{label}: invalid JSON ({exc.msg} at line {exc.lineno})") from exc
    if not isinstance(data, dict):
        raise SchemaError(f"{label}: top level must be an object")
    return data
