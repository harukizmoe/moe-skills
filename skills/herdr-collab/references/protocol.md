# Protocol notes (maintainers)

Design decisions behind `herdr-collab`, kept out of SKILL.md so the agent-facing
surface stays lean. See `herdr` skill docs for full CLI semantics.

## Why verification is a separate step

`herdr agent list` output is a snapshot. Between discovery and prompt the peer may
have been prompted by another client, exited, or moved. `agent get` on the resolved
target is the only cheap re-check; the skill treats it as mandatory because a prompt
into an exited name fails, and a prompt into a `working` peer queues noise into an
active turn.

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

## blocked is human territory

`blocked` means the peer sits at an approval or question dialog. The skill's contract:
read it, surface it verbatim, wait for the human. Two agents auto-approving each
other's dialogs is the failure mode this rule exists to prevent.

## Known limitations

- Cross-machine (`--machine`) peers are out of scope for 0.1.0; the skill assumes a
  single session. Extending discovery/filtering to saved machines is a candidate for
  0.2.0.
- No concurrency limit is enforced by Herdr itself; the one-in-flight rule is a skill
  convention to keep peer transcripts readable.
