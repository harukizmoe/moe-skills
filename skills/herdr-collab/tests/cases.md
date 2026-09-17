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
  `agent wait --until idle` (bounded) or reports "peer busy" to the user.
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

## CASE: oversized response

Given:
  peer output exceeds what a large recent-unwrapped read returns

Expected:
  Follow-up prompt asking the peer to write Markdown to a temp file and reply
  with the path; read the file locally.
  MUST NOT put the file handoff in the initial prompt.
