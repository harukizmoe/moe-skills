# Protocol notes (maintainers)

Design decisions behind `herdr-collab`, kept out of SKILL.md so the agent-facing
surface stays lean. This document covers why the standalone skill combines Herdr
layout control with guarded multi-agent collaboration.

## Why verification is a separate step

`herdr agent list` output is a snapshot. Between discovery and prompt the peer may
have been prompted by another client, exited, or moved. `agent get` on the resolved
target is the only cheap re-check; the skill treats it as mandatory because a prompt
into an exited name fails, and a prompt into a `working` peer queues noise into an
active turn.

## Why the caller is excluded

`herdr agent list` includes the calling agent, so the caller's own `pane_id` must
be removed before candidate selection. A named target that resolves to
`$HERDR_PANE_ID` is a self-target and must be rejected. `agent get` exposes the
verified record under `.result.agent`, including `.agent_status` and `.pane_id`.

## Why targets are names or pane IDs only

The CLI accepts unique live agent names and pane IDs hosting agents. Names follow
the pane occupant and clear on exit; pane IDs are stable but change when a pane
moves workspaces. Everything else a human might use to point at a pane (kind,
terminal title, sidebar position) is ambiguous across workspaces and rejected here.

## Wait semantics relied upon

- `agent prompt --wait` settles on first `idle`/`done`/`blocked`; the caller timeout
  includes submission time; `agent_prompt_stalled` means no observed activity within
  5s of submission.
- Settled wait tracks lifecycle, not turns: prompting an already-working agent may
  return when the current turn ends. This is why the skill refuses to auto-prompt
  working peers instead of relying on the gate.
- Timeout/stall does not prove non-delivery; the skill mandates inspect-before-resubmit.
- Busy-peer waits request `idle`, `done`, `blocked`, and `unknown`; only `idle`/`done` are ready for a new prompt.

## blocked is human territory

`blocked` means the peer sits at an approval or question dialog. The skill's contract:
read it, surface it verbatim, wait for the human. Two agents auto-approving each
other's dialogs is the failure mode this rule exists to prevent.

## Scope boundaries

- Saved-machine control is supported only with an explicit, consistently reused
  `--machine` selector; local caller IDs are never used to auto-select remote peers.
- The one-in-flight rule is a skill convention; Herdr itself does not enforce it.
- Layout defaults preserve the caller's cwd and focus; users must explicitly request
  a different workspace, tab, worktree, or cwd.
