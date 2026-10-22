# Changelog

All notable changes to the `ai-workflow-bootstrap` skill.
Format: Keep a Changelog; versioning: SemVer. Versions are tagged
`ai-workflow-bootstrap/vX.Y.Z`.

## 0.3.0 - 2026-10-22

- **Who did the work is now part of the record.** A handoff requires `author` and
  `author_role`, a review requires `reviewer` and `reviewer_role`; both are
  role-checked (`developer` to hand off, `reviewer` to approve). The gate refuses
  a review whose reviewer is the handoff's author (`review-self`), and
  `wfcheck review` refuses at record time with both names in the message.
- Why: the gate could not previously distinguish a developer's work from the
  coordinator's. An agent that wrote the implementation itself — instead of
  delegating it — produced evidence and a passing gate, and no artifact said so.
  A local check still cannot prove who typed the code; recording the identity
  makes the claim explicit, attributable, and refusable when it contradicts
  itself.
- `finish` and `handoff` gained a required `--author`; `review` gained a required
  `--reviewer`. Existing handoffs and reviews without these keys are rejected on
  load, so a project upgrading to 0.3.0 must re-record them (or the tasks must be
  re-handled, which is the honest outcome: those claims never named anyone).
- The developer and reviewer role definitions now say so, and the developer must
  sign with the name it was spawned as rather than a role word.

## 0.2.0 - 2026-10-22

- **The loop is one command.** `wfcheck finish --task T` runs every declared
  command, records the real exit codes, writes the handoff, commits the state, then
  gates — including re-running the evidence. The previous five-step manual sequence
  (run, commit, handoff, commit, gate) was a place to get the order wrong, and the
  most common failure — recording evidence before the last edit — was a direct
  consequence of it being manual. `finish` refuses uncommitted work and refuses to
  write a handoff when a command failed, while keeping the failed record.
- **Everything the workflow owns now lives under `.ai-workflow/`**: `gate/`, `bin/`,
  `config.sh`, and the records. Previously it wrote `tools/` and `scripts/` at the
  project root, where a project's own `scripts/test.sh` was silently replaced while
  `scripts/config.sh` was protected. Nothing appears at the project root now.
- **The installer keeps the record directories alive through a clone** by writing
  `.gitkeep`. `evidence/`, `handoffs/`, and `reviews/` are empty until the first
  task, and git does not track empty directories, so a fresh checkout looked like a
  broken install.
- Review is required only over `WF_REVIEW_MAX` changed lines (default 400). Size is
  computed from git over the task's range, excluding `.ai-workflow/`, walking back
  over trailing state-only commits — so it cannot be declared and is not hidden by
  how a task's commits are split. A state-only handoff commit is bookkeeping, not
  unreviewed work.
- The gate no longer fails before reading evidence when a project has configured no
  command; the command comparison is the one check skipped in that case.

## 0.1.0 - 2026-10-22

- Initial release. Installs a repository-level gate into a new or existing project,
  language-agnostically: the gate, entry points, `AGENTS.md`, the `.ai-workflow/`
  skeleton, and three agent role definitions.
- The gate refuses agent self-reports by artifact, not by prose: missing evidence,
  evidence recorded before a later edit, a record naming a command the project does
  not declare, approval of one commit and gating of another, and any command that
  fails when re-run.
- Task state is derived from handoff, review, and git ancestry, so there is no
  stored status field to forge; `merge`, `state`, and merge records do not exist.
- Verification commands come only from `.ai-workflow/config.sh`: no `--command`
  flag, and `WF_*` environment variables are ignored.
- `install.sh` is idempotent and never overwrites an existing file.
