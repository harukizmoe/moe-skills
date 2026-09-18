---
name: herdr-collab
description: "Control Herdr and coordinate coding agents across workspaces, tabs, and panes: inspect layout, create panes, run commands, start agents, discover peers, verify identity and availability, hand off work with prompt --wait, and read results back. Use when the user explicitly asks to use Herdr for panes, workspaces, commands, agents, or multi-agent collaboration and HERDR_ENV=1."
license: MIT
compatibility: "Requires the herdr CLI (>= 0.9.0) on PATH and HERDR_ENV=1. Agent kinds follow the installed herdr build."
metadata:
  version: 0.1.2
  owner: harukizmoe
  source: https://github.com/harukizmoe/moe-skills
---

# herdr-collab

Control Herdr and coordinate coding agents across its workspaces, tabs, and panes.
This standalone skill covers CLI discovery, layout management, pane commands, agent
startup, peer selection, work handoff, waiting, and result collection. It includes
the collaboration hardening rules below and does not require another skill for any
supported operation. Use the installed Herdr CLI as the runtime authority.
Requests outside the installed CLI's supported operations are reported to the user;
never delegate them to another skill.

## Gate: you must be inside Herdr

Before any command, verify the calling context:

```bash
test "${HERDR_ENV:-}" = 1
```

If it fails, you are not running inside a Herdr-managed pane. Tell the user and stop.
Do not inspect or control a Herdr session from outside Herdr.

## CLI authority

This skill is self-contained and treats the installed `herdr` binary as the only
CLI authority. After the gate passes, learn syntax from:

```bash
herdr --help
herdr agent
herdr pane
herdr workspace
herdr tab
herdr worktree
herdr terminal
herdr notification
herdr integration
herdr session
herdr machine
```

Do not run bare `herdr` for discovery; it can launch or attach the TUI. Do not
probe a mutating nested command by omitting arguments. Most commands return JSON:
read identifiers and state from those responses instead of predicting them.

Before relying on newer behavior, run `herdr status` and check client/server
compatibility. A missing method is a compatibility signal, not permission to stop or
upgrade the server.

## Vocabulary

- **Caller**: you — the agent whose pane runs these commands. Identified by
  `$HERDR_WORKSPACE_ID`, `$HERDR_TAB_ID`, `$HERDR_PANE_ID`.
- **Peer**: another recognized coding agent occupying a pane. Target peers by the
  pane ID hosting them (`w1R:p2`) or by their unique live agent name. Never target
  by agent kind ("codex"), terminal title, or sidebar order.
- **Peer states**: `idle`/`done` = ready for input; `working` = busy; `blocked` =
  waiting at an approval or question dialog; `unknown` = present but unclassifiable.

Herdr distinguishes `done` from `idle` using server-seen state. Explicit focus can
mark a completion seen; reading output does not. Treat both as prompt-eligible only
after the mandatory `agent get` re-check, and do not infer completion from either
state without reading the result.

Server-reported `agent_status` can be stale or wrong: a peer running a long turn or
background job may still be reported `idle`. When reported state and visible screen
evidence (spinner, progress bar, "Waiting for …", running background job) disagree,
the screen wins and the peer is treated as `working`.

## Herdr objects and IDs

Workspaces, tabs, and panes describe terminal layout; an agent is the recognized
coding process occupying a pane. A pane may exist without an agent. `agent start`
requires an available shell pane and never creates, splits, or moves layout.

After `pane move`, prefer `.result.move_result.pane.pane_id`; the previous ID is
reported as `.result.move_result.previous_pane_id` and must not be reused as a
general target.

Agent commands accept only a unique live agent name or the pane ID currently hosting
that agent. Names match `[a-z][a-z0-9_-]{0,31}`, follow the pane occupant, and clear
when that agent exits, is released, or is replaced. IDs are opaque and scoped to one
Herdr server. A pane move gives it a new workspace-qualified pane ID; after a move,
use the returned live ID or agent name, never the previous general target.

Public IDs are opaque handles; closed pane and tab IDs are not reused. An omitted
`pane split` target uses the caller's pane when `$HERDR_PANE_ID` is available;
otherwise it uses the focused pane, so this skill always supplies `--current` or an
explicit target.

The caller context is injected into a managed pane:

```bash
printf '%s\n' "$HERDR_WORKSPACE_ID" "$HERDR_TAB_ID" "$HERDR_PANE_ID"
```

Use `--current` for commands targeting the caller's pane. Do not rely on another
client's focused pane. Discover live layout with:

```bash
herdr workspace list
herdr tab list --workspace "$HERDR_WORKSPACE_ID"
herdr pane current --current
herdr pane list --workspace "$HERDR_WORKSPACE_ID"
herdr agent list
```

Creation responses are authoritative: read `.result.workspace`, `.result.tab`,
`.result.root_pane`, or `.result.pane` fields as returned. Never derive IDs from
sidebar order, examples, or predicted numbering.

For user-facing reports, resolve IDs to human-readable names: workspace labels
from `workspace list` (`.label`), tab labels from `tab list` (`.label`), and pane
names from `terminal_title` / `terminal_title_stripped` rows that discovery
commands already return. Present "workspace「planeweaver」→ tab 1 → pane「主会话」",
not bare IDs. These names are display-only: commands still address panes by
`--current`, pane ID, or live agent name — never by title or label.

## Machine and session scope

Without `--machine`, all IDs and agent names belong to the inherited local Herdr
server and session. A saved SSH machine is a separate namespace. If remote control
is requested, use the same global selector for discovery and every later command:

```bash
herdr machine list
herdr --machine <label-or-id> agent list
herdr --machine <label-or-id> pane list
herdr --machine <label-or-id> agent prompt <agent> "<task>" --wait --timeout 120000
```

The selector must be an enabled saved profile ID or a unique case-sensitive label,
not an arbitrary SSH hostname. Do not combine `--machine` with `--session` or
`--remote`; remote forwarding does not install, start, or restart a server and never
falls back to Local. A connection failure does not prove a mutation was not applied:
inspect remote state before retrying. Do not add, remove, enable, or disable machine
profiles unless the user asks.

`herdr machine list` lists saved connection profiles, not a cross-machine pane
inventory. CLI responses are JSON by default; `machine list` additionally accepts
`--json` for scripted consumption. Remote worktree paths must be absolute, `~`,
or start with `~/`; plugin link paths must be absolute. Remote forwarding does not
forward local configuration, session management, installation, or interactive attach.
Setup that would replace an incompatible remote server requires the user's consent.

The local `$HERDR_PANE_ID` identifies only the inherited local session. For a remote
machine, do not compare it with remote pane IDs or auto-select a remote peer; use an
explicit remote target and verify it in that machine's namespace.

## Create layout and start an agent

When the user asks for a new agent and does not specify a topology, use a sibling
pane in the current tab and preserve the caller's working directory. Do not create a
workspace, tab, worktree, or different cwd unless requested. Inspect the caller's
layout first:

```bash
herdr pane layout --pane "$HERDR_PANE_ID"
```

Honor a direction requested by the user. Otherwise split a wide pane to the right and
a narrow or tall pane down. Keep the user's focus in the caller pane and use
`--no-focus` for background work:

```bash
herdr pane split --current --direction right --cwd "$PWD" --no-focus
```

Use `down` instead of `right` when the layout needs a new row. Avoid repeated splits
that create unusably narrow columns or short rows. Read the new pane from
`.result.pane.pane_id`; never predict it.

The target pane must be an available shell at its interactive prompt, with no
foreground command, editor, or agent. Discover supported agent kinds with
`herdr agent`. Start the requested kind with a useful unique name:

```bash
herdr agent start <name> --kind <kind> --pane <new-pane-id>
```

Pass native agent arguments only after `--`. A successful start returns after Herdr
detects the agent and considers it ready. If it returns `agent_not_ready`, keep the
name, inspect it, and wait for `idle` before prompting. After startup, run the normal
verification in Step 2; a newly started agent is still not a verified handoff target.

The startup wait defaults to 30000 ms and accepts a bounded `--timeout` up to the
installed CLI's limit. Use the kind requested by the user; do not infer a kind from
the pane title or neighboring agents.

If the user explicitly requests a new workspace or tab, use the installed command
syntax and keep the caller's focus unchanged unless asked otherwise:

```bash
herdr workspace create --cwd "$PWD" --no-focus
herdr tab create --workspace <workspace-id> --cwd "$PWD" --no-focus
```

Read the returned `.result.workspace`, `.result.tab`, and `.result.root_pane` fields
before any follow-up command. Do not create a workspace, tab, worktree, or different
cwd merely to obtain another agent pane.

Do not close, replace, or rearrange panes, tabs, workspaces, or sessions you did not
create unless the user explicitly asks and the target is verified.

## Run an ordinary command in another pane

For a command that does not need an agent, create a sibling pane with the same
geometry and focus rules, then use the pane surface:

```bash
herdr pane split --current --direction right --cwd "$PWD" --no-focus
herdr pane run <returned-pane-id> "<command>"
herdr pane wait-output <returned-pane-id> --match "<literal>" --timeout 120000
herdr pane read <returned-pane-id> --source recent-unwrapped --lines 120
```

Read `.result.pane.pane_id` from the split response. `pane run` atomically sends
command text and Enter. Use `--regex` instead of `--match` only when a literal
substring is insufficient. `pane wait-output` searches the selected snapshot
immediately, so already-produced output can match. Omit a timeout only when an
indefinite wait is intentional. Replace `right` with `down` when the requested or
inspected geometry calls for a new row.

Use `agent send-keys <agent> <key>` for deliberate interactive agent controls such
as `esc` or `ctrl+c`; do not use raw terminal input for ordinary agent handoff.

## Step 1 — Discover peers

List all live agents in the session, then filter:

```bash
herdr agent list
```

Each row carries `agent` (name), `agent_status`, `pane_id`, `workspace_id`, `cwd`.

Resolution rules, applied in order:

0. **Reject named self-targets**: when the user named a peer, resolve it once
   before choosing it. If its `pane_id` equals `$HERDR_PANE_ID`, reject it as a
   self-target and stop.
1. **Exclude the caller from automatic candidates**: discard the row whose
   `pane_id` equals `$HERDR_PANE_ID`. The caller is never an automatic peer.
2. **Named target**: if the user named the peer (a live agent name or a pane ID),
   use exactly that. If it does not resolve, report the failure — never silently
   substitute another peer.
3. **Same-workspace preference**: when the user says "another agent", "another
   instance", or names no target, restrict candidates to
   `$HERDR_WORKSPACE_ID` first. Choose a peer in a different workspace only when
   no eligible same-workspace peer exists, and say so explicitly.
4. **Eligibility**: only `idle` or `done` peers may receive a prompt — and the
   reported state must survive the screen cross-check in Step 2. A peer whose
   screen shows a spinner, progress bar, "Waiting for …", or a running
   background job is `working` regardless of `agent_status`; treat it as
   ineligible and tell the user that the server status was wrong.
5. **MUST NOT auto-select a working peer.** If every candidate is `working`,
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

Check `.result.agent.agent_status` and `.result.agent.pane_id`. The status must be
`idle` or `done`, and the pane must not equal `$HERDR_PANE_ID`. If either check
fails, return to Step 1's eligibility rules. If the target no longer resolves,
the agent exited — report that and re-discover.

Then cross-check the reported state against the screen — `agent_status` can be
stale or wrong, and a reported-`idle` peer may be mid-turn:

```bash
herdr agent read <peer> --source recent-unwrapped --lines 40
```

A spinner, progress bar, "Waiting for …", running background job, or an open
editor in that output means the peer is `working` (or otherwise occupied) no
matter what `agent_status` says. Treat it as ineligible. Report the
disagreement between the server state and the screen to the user; if the
runtime reports issues programmatically, file that report too. Only a screen
that ends at an idle prompt marks the peer prompt-eligible.

The same read doubles as the identity check: confirm the peer is the agent you
think it is (right repo, right context) before handing off substantive work.

## Step 3 — Hand off work

Submit a self-contained prompt. The peer does not see your conversation; include
everything it needs (repo path, branch, what to do, what to report back):

```bash
herdr agent prompt <peer> "<self-contained task + 'Report findings as a short list.'>" --wait --timeout 300000
```

`--wait` returns on the first settled `idle`, `done`, or `blocked` state and is
enough for normal handoffs. The prompt surface honors the pane's bracketed-paste
mode and submits the text plus encoded Enter as one ordered handoff. Accepted
submission does not prove that a turn started. From a non-working state, `--wait`
requires observed `working` or `blocked` activity within Herdr's activity gate; the
caller timeout includes submission time, and the settled wait tracks lifecycle state
rather than one exact turn. Use `--until` only for a state-specific workflow; normal
handoffs need the default wait. It reports `agent_prompt_stalled` when no activity
follows submission, and `timeout` when your timeout expires first.
A stall can be a false alarm: a fast agent may answer and settle back to `idle` before
the activity gate samples a `working` state. A timeout or stall does not prove the
prompt was never delivered — inspect before re-submitting:

```bash
herdr agent get <peer>
herdr agent read <peer> --source recent-unwrapped --lines 120
```

If the peer is already `working`, do not prompt it now. Either:

```bash
herdr agent wait <peer> --until idle --until done --until blocked --until unknown --timeout 300000
```

If it settles `idle` or `done`, verify and prompt. If it settles `blocked`, read
the approval or question dialog, surface it to the user, and wait for the user's
decision. If it settles `unknown`, inspect with `agent get` and report the peer
as ineligible. On timeout, report "peer busy" to the user. Never queue the task
by sending it into a working, blocked, or unknown agent.

If `agent prompt --wait` reports `blocked`, the peer is at an approval or question
dialog. Read its screen, surface the question to the user, and wait for the user's
decision. NEVER answer another agent's approval dialog yourself.

If `agent prompt` rejects the request with `agent_blocked` before sending, inspect
the blocked UI and ask the user; never answer the approval or question yourself.

## Read sources

Choose the smallest surface that answers the question:

- `visible`: the currently rendered viewport;
- `recent`: recent rendered output, including soft wraps;
- `recent-unwrapped`: recent output with soft wraps joined; prefer it for logs and
  transcripts;
- `detection`: the plain-text bottom-buffer snapshot used for agent detection.

Use `--format ansi` only when colors or terminal styling are evidence. Alternate
screen rows may not be in ordinary host scrollback; a larger `--lines` request does
not guarantee that every application-owned response can be recovered.

Two rendering caveats when reading another pane's result back:

- An agent renders long tool output inside collapsible boxes; the on-screen
  transcript shows `… (N earlier lines, showing 10 of M) ⟨Ctrl+O: Expand⟩` and
  the hidden lines are absent from every `pane read`/`agent read` snapshot. A
  bigger `--lines` does not recover them. If those hidden lines matter, ask the
  peer to restate the conclusion as chat text or write it to a file.
- A `--lines` budget can still cut a long transcript at its top; treat the first
  visible line as a cursor, not the beginning.

For supported idle agents, Herdr may collect application-owned history and restore
the viewport afterward; this is not guaranteed for every application or response.

## Step 4 — Read the result

After the wait settles, read the peer's answer:

```bash
herdr agent read <peer> --source recent-unwrapped --lines 200
```

If the response is longer than what a large read returns, ask the peer (in a
follow-up prompt) to write the full result as Markdown to a file under a
temporary directory and reply with only the path; then read that file on the
same machine. Use this only as a fallback, not in the initial prompt.

Report the peer's findings to the user with attribution using human-readable
names — "peer「数据处理」 (workspace planeweaver, pane w1R:p7) reported: …" —
resolving labels and titles per "Herdr objects and IDs". Never present a
peer's output as your own work.

## Peer state reference

| State | Meaning | Your action |
|---|---|---|
| `idle` / `done` | reported ready for input | verify, cross-check the screen, then prompt |
| `working` | mid-turn | `agent wait --until idle --until done --until blocked --until unknown`; never auto-prompt |
| `blocked` | approval/question dialog | read screen, ask the human, never answer it |
| `unknown` | unclassifiable | treat as ineligible; investigate with `agent get` |
| screen shows activity while reported `idle` | server state is stale or wrong | treat as `working`; report the disagreement to the user |

## Hard rules

- Gate on `HERDR_ENV=1` before anything; never control Herdr from outside.
- Target peers only by live agent name or hosting pane ID — never by kind,
  title, or order.
- Never treat the caller's own pane as a peer or prompt it.
- Only prompt peers in `idle`/`done`. NEVER auto-select or auto-prompt a
  `working`, `blocked`, or `unknown` peer.
- When `agent_status` and the peer's screen disagree, the screen wins; treat the
  peer as `working` and tell the user the server status was wrong.
- One in-flight prompt per peer at a time; re-submit only after inspecting
  state following a timeout or stall.
- A peer's approval dialog belongs to the human. Read it, surface it, wait.
- Do not close, replace, or rearrange panes, tabs, workspaces, or sessions you did not
  create unless the user explicitly asks and the target is verified.
- Attribute peer output to the peer, using human-readable names (workspace label,
  tab label, terminal title) in user-facing reports; keep command addressing on
  `--current`/pane ID/agent name.
- Use `--no-focus` for background layout work unless the user asks to change focus.
- Use `--current`, an explicit pane ID, or a unique agent name; never rely on UI focus.
- Parse IDs from JSON responses; never derive them from sidebar order or examples.
- Use `--trust-repository` only after the user has verified the repository; it is not
  a routine retry for a failed worktree command.
- Never run `herdr server stop` from an active session unless the user explicitly
  intends to stop the server and its pane processes.
- Never kill the main Herdr process. Use a named test session for isolated experiments.
  Do not use `workspace close --group` merely to bypass a close-safety error.
- A remote mutation or connection error requires state inspection before retrying.
- Do not claim a peer task completed from lifecycle state alone; read and attribute
  the resulting output.
