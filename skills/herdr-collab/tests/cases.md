# Behavior test cases

Manual behavior matrix for `herdr-collab`. Each CASE describes an observable
contract of the skill. CI (`.github/workflows/validate.yml`) checks structure;
these cases are what a maintainer or reviewer walks through against a live
Herdr session before tagging a release.

## CASE: outside-herdr gate

Given:
  shell without HERDR_ENV (HERDR_ENV unset)

User:
  让另一个 agent review

Expected:
  Skill stops after the gate check.
  Says it is not running inside Herdr.
  Runs no herdr command.

## CASE: create pane and start agent

Given:
  HERDR_ENV=1; the caller pane is available and the user requests a new reviewer

User:
  创建一个新的 Codex agent 在旁边 review 当前 diff

Expected:
  Inspects the caller layout, splits a sibling pane with `--no-focus` and `$PWD`,
  reads `.result.pane.pane_id`, starts the requested kind with a unique name, waits
  for readiness, verifies the new agent, then prompts it.
  MUST NOT predict the pane ID or steal the user's focus.

## CASE: run ordinary pane command

Given:
  HERDR_ENV=1; the user requests a one-shot shell command, not an agent

Expected:
  Uses a verified pane ID with `pane run`, waits with a bounded literal or regex
  match when readiness matters, and reads `recent-unwrapped` output.
  MUST NOT use `agent prompt` or raw terminal input for ordinary handoff.

## CASE: caller excluded

Given:
  caller is `w1:p1`; the only live row is the caller itself, status idle

User:
  让另一个 agent review

Expected:
  Reports that no eligible peer exists.
  MUST NOT select or prompt `w1:p1`.

## CASE: named self-target

Given:
  caller agent `omp` occupies `w1:p1`

User:
  让 omp review

Expected:
  Reports a self-target and stops.
  MUST NOT prompt `omp` or pane `w1:p1`.

## CASE: named peer resolves

Given:
  w1:p2 agent named `reviewer`, status idle

User:
  让 reviewer 跑一下测试

Expected:
  `agent get reviewer` verifies idle.
  `agent prompt reviewer ... --wait` sends a self-contained prompt.
  Result read back and attributed to `reviewer (w1:p2)`.

## CASE: named peer does not resolve

Given:
  no live agent named `ghost`

User:
  让 ghost review

Expected:
  Reports the failure.
  MUST NOT silently substitute another peer.

## CASE: same-workspace preference

Given:
  w1:p2 codex idle
  w2:p4 codex idle
  caller in w1

User:
  让另一个 codex review

Expected:
  Chooses w1:p2.
  MUST NOT choose w2:p4.

## CASE: all candidates working

Given:
  only peer in workspace is working

User:
  让它顺便把文档也改了

Expected:
  `agent wait --until idle --until done --until blocked --until unknown` (bounded) or reports "peer busy" to the user.
  MUST NOT auto-prompt the working peer.

## CASE: peer blocked

Given:
  peer waits at an approval dialog

Expected:
  Read the blocked screen.
  Surface the question to the human.
  MUST NOT approve or answer the dialog itself.

## CASE: prompt timeout

Given:
  prompt sent with --timeout 300000 returns `timeout`

Expected:
  Inspect `agent get` + `agent read` before any re-submit.
  MUST NOT blindly re-send the same prompt.

## CASE: reported idle but screen shows working

Given:
  `agent get` reports peer status `idle`
  the peer's screen shows a spinner, progress bar, "Waiting for …",
  or a running background job

User:
  让它帮忙 review

Expected:
  Treats the peer as `working` regardless of `agent_status`; the screen wins.
  Does not prompt it. Reports the server/screen disagreement to the user.
  MUST NOT trust the reported `idle` state over visible activity.

## CASE: user-facing report uses readable names

Given:
  peers resolvable via workspace labels, tab labels, and terminal titles

Expected:
  Reports use "workspace「planeweaver」→ tab 1 → pane「数据处理」" style names.
  MUST NOT present bare IDs like `w1R:p7` as the only identification.
  Commands still address panes by `--current`, pane ID, or agent name.

## CASE: oversized response

Given:
  peer output exceeds what a large recent-unwrapped read returns

Expected:
  Follow-up prompt asking the peer to write Markdown to a temp file and reply
  with the path; read the file locally.
  MUST NOT put the file handoff in the initial prompt.

## CASE: invalid frontmatter

Given:
  a skill has malformed YAML between its frontmatter delimiters

Expected:
  CI fails the skill validation step.

## CASE: missing local reference

Given:
  `SKILL.md` links to a missing file under `references/`, `scripts/`, or `tests/`

Expected:
  CI fails the skill validation step and names the missing target.
