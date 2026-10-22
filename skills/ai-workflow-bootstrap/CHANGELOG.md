# Changelog

All notable changes to the `ai-workflow-bootstrap` skill.
Format: Keep a Changelog; versioning: SemVer. Versions are tagged
`ai-workflow-bootstrap/vX.Y.Z`.

## 0.1.0 - 2026-10-22

- Initial release. Installs a repository-level gate into a new or existing project,
  language-agnostically: `tools/wfcheck/`, `scripts/`, `AGENTS.md`, `.ai-workflow/`,
  and three agent role definitions.
- The gate refuses agent self-reports by artifact, not by prose: missing evidence,
  evidence recorded before a later edit, a record naming a command the project does
  not declare, approval of one commit and gating of another, and any command that
  fails when re-run.
- Task state is derived from handoff, review, and git ancestry, so there is no
  stored status field to forge; `merge`, `state`, and merge records do not exist.
- Review is required only over `WF_REVIEW_MAX` changed lines (default 400). Size
  is computed from git over the task's range, excluding `.ai-workflow/`, walking
  back over trailing state-only commits, so it cannot be declared and is not
  hidden by how a task's commits are split.
- Verification commands come only from `scripts/config.sh`: no `--command` flag,
  and `WF_*` environment variables are ignored.
- `scripts/install.sh` is idempotent and never overwrites an existing file.
