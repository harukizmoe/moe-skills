---
name: herdr-collab
description: "Coordinate multiple coding agents across Herdr workspaces and panes: discover sibling or cross-workspace peers, verify their identity and availability, hand off work with prompt --wait, and read results back. Use when the user asks to have another agent review, implement, or check something; to delegate work to another pane or workspace; or to collect a peer agent's status or output. Only when the agent explicitly mentions Herdr, panes, or multi-agent collaboration and HERDR_ENV=1."
license: MIT
compatibility: "Requires the herdr CLI (>= 0.9.0) on PATH and HERDR_ENV=1. Agent kinds follow the installed herdr build."
metadata:
  version: 0.1.0
  owner: harukizmoe
  source: https://github.com/harukizmoe/moe-skills
---

# herdr-collab

Coordinate work with other coding agents running in neighboring Herdr panes or other
workspaces of the same Herdr session. This skill covers peer discovery, verification,
work handoff, and result collection. It does not cover Herdr layout management itself —
for creating panes or starting agents from scratch, use the `herdr` skill first, then
apply this skill to collaborate.

## Gate: you must be inside Herdr

Before any command, verify the calling context:

```bash
test "${HERDR_ENV:-}" = 1
```

If it fails, you are not running inside a Herdr-managed pane. Tell the user and stop.
Do not inspect or control a Herdr session from outside Herdr.

## Vocabulary

- **Caller**: you — the agent whose pane runs these commands. Identified by
  `$HERDR_WORKSPACE_ID`, `$HERDR_TAB_ID`, `$HERDR_PANE_ID`.
- **Peer**: another recognized coding agent occupying a pane. Target peers by the
  pane ID hosting them (`w1R:p2`) or by their unique live agent name. Never target
  by agent kind ("codex"), terminal title, or sidebar order.
- **Peer states**: `idle`/`done` = ready for input; `working` = busy; `blocked` =
  waiting at an approval or question dialog; `unknown` = present but unclassifiable.

## Step 1 — Discover peers

List all live agents in the session, then filter:

```bash
herdr agent list
```

Each row carries `agent` (name), `agent_status`, `pane_id`, `workspace_id`, `cwd`.

Resolution rules, applied in order:

1. **Named target**: if the user named the peer (a live agent name or a pane ID),
   use exactly that. If it does not resolve, report the failure — never silently
   substitute another peer.
2. **Same-workspace preference**: when the user says "another agent", "another
   instance", or names no target, restrict candidates to
   `$HERDR_WORKSPACE_ID` first. Choose a peer in a different workspace only when
   no eligible same-workspace peer exists, and say so explicitly.
3. **Eligibility**: only `idle` or `done` peers may receive a prompt.
4. **MUST NOT auto-select a working peer.** If every candidate is `working`,
   `blocked`, or `unknown`, do not pick the "least busy" one. Either wait (Step 3)
   or surface the situation to the user.

When several same-workspace peers are eligible, prefer one whose `cwd` relates to
the task's repository; otherwise list the candidates and let the user choose.

Cross-workspace discovery (peers anywhere in the session) is the same command;
`herdr agent list` already spans every workspace. Filter `workspace_id` yourself.

## Step 2 — Verify the peer before prompting

Never prompt an unverified target. Confirm it still exists and is eligible —
state can change between discovery and use:

```bash
herdr agent get <peer>
```

Check `.result.agent_status`. If it is not `idle` or `done`, return to Step 1's
eligibility rules. If the target no longer resolves, the agent exited — report
that and re-discover.

Skim recent output to confirm the peer is the agent you think it is (right repo,
right context) before handing off substantive work:

```bash
herdr agent read <peer> --source recent-unwrapped --lines 40
```

## Step 3 — Hand off work

Submit a self-contained prompt. The peer does not see your conversation; include
everything it needs (repo path, branch, what to do, what to report back):

```bash
herdr agent prompt <peer> "<self-contained task + 'Report findings as a short list.'>" --wait --timeout 300000
```

`--wait` returns on the first settled `idle`, `done`, or `blocked` state and is
enough for normal handoffs. It reports `agent_prompt_stalled` when no activity
follows submission, `timeout` when your timeout expires first. A stall can also
be a false alarm: a fast agent may answer and settle back to `idle` before the
5-second activity gate samples a `working` state. A timeout or
stall does not prove the prompt was never delivered — inspect before re-submitting:

```bash
herdr agent get <peer>
herdr agent read <peer> --source recent-unwrapped --lines 120
```

If the peer is already `working`, do not prompt it now. Either:

```bash
herdr agent wait <peer> --until idle --timeout 300000
```

then verify and prompt, or report "peer busy" to the user. Do not queue the task
by sending it into a working agent.

If `agent prompt` or `agent wait` reports `blocked`, the peer is at an approval
or question dialog. Read its screen, surface the question to the user, and wait
for the user's decision. NEVER answer another agent's approval dialog yourself.

## Step 4 — Read the result

After the wait settles, read the peer's answer:

```bash
herdr agent read <peer> --source recent-unwrapped --lines 200
```

If the response is longer than what a large read returns, ask the peer (in a
follow-up prompt) to write the full result as Markdown to a file under a
temporary directory and reply with only the path; then read that file on the
same machine. Use this only as a fallback, not in the initial prompt.

Report the peer's findings to the user with attribution ("peer <peer> on
<pane_id> reported: …"). Never present a peer's output as your own work.

## Peer state reference

| State | Meaning | Your action |
|---|---|---|
| `idle` / `done` | ready for input | verify, then prompt |
| `working` | mid-turn | `agent wait --until idle`; never auto-prompt |
| `blocked` | approval/question dialog | read screen, ask the human, never answer it |
| `unknown` | unclassifiable | treat as ineligible; investigate with `agent get` |

## Hard rules

- Gate on `HERDR_ENV=1` before anything; never control Herdr from outside.
- Target peers only by live agent name or hosting pane ID — never by kind,
  title, or order.
- Only prompt peers in `idle`/`done`. NEVER auto-select or auto-prompt a
  `working`, `blocked`, or `unknown` peer.
- One in-flight prompt per peer at a time; re-submit only after inspecting
  state following a timeout or stall.
- A peer's approval dialog belongs to the human. Read it, surface it, wait.
- Do not close panes, tabs, workspaces, or sessions you did not create.
- Attribute peer output to the peer.
