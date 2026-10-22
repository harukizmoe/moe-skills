---
name: ai-workflow-bootstrap
description: "Initialise a repository-level AI coding workflow in a project you are starting: a gate that refuses agent self-reports, evidence bound to a content hash, reviews that name the commit they judged, and role definitions for architect / developer / reviewer. Use when starting a new project, when a directory has code but no .ai-workflow/, when asked to set up or initialize the workflow, or when an agent keeps claiming work is done without proof. Language-agnostic: Go, Rust, Node, Python, or polyglot."
license: MIT
compatibility: "Requires git, sh, and Python 3.8+. Tested on Linux and macOS. Installs into a repository of any language."
metadata:
  version: 0.3.0
  owner: harukizmoe
  source: https://github.com/harukizmoe/moe-skills
---

# Bootstrap the workflow

You are installing a **gate** into a project, not writing process prose for an
agent to follow. The gate is what makes the process hold: it does not read claims,
it re-runs commands and compares git objects.

The assets sit next to this file; install them rather than retyping them:

| Path | Contents |
| --- | --- |
| `tools/wfcheck/` | the gate: reads git and JSON, writes only artifacts |
| `scripts/` | `install.sh` and the entry points, copied into `.ai-workflow/bin/` |
| `templates/` | what gets copied into the project |
| `.omp/agents/` | architect / developer / reviewer definitions |

## What this buys

An agent's report is a claim. Without the gate, "tests pass" and "I implemented
it" are indistinguishable from an agent that ran nothing. The gate makes those
two cases measurably different:

| Situation | Refused as |
| --- | --- |
| Claimed success, no recorded run | `evidence-missing` |
| Evidence recorded before a later edit | `evidence-stale` |
| A record naming a command the project never declared | `evidence-command` |
| Approval of commit A, gate of commit B | `review-stale` |
| A command that fails when the gate re-runs it | `rerun FAILED` |
| A task "marked done" without artifacts | impossible: state is derived |

## Install

From this skill's directory:

```sh
sh scripts/install.sh <project-dir>
```

Safe on an empty directory, safe to re-run, never overwrites an existing file.
Everything it installs lives under `.ai-workflow/` — `gate/`, `bin/`, `config.sh`,
and the records — plus an `AGENTS.md` and `.omp/agents/`. Nothing appears at the
project root, so your own `scripts/` or `config.sh` is never shadowed.

Then, in the project:

1. `git init` if it is not a repository yet, and commit the skeleton. The gate
   compares commits; before the first one there is nothing to compare.
2. Edit `.ai-workflow/config.sh` so `WF_TEST` / `WF_CHECK` name this project's real
   commands. Leave them empty to let detection pick a toolchain (Go, Cargo, Bun,
   npm, pytest, Make). If detection is wrong or absent, set them explicitly:
   empty and undetectable means the gate refuses rather than guessing, which is
   the correct behavior.
3. `PYTHONPATH=.ai-workflow/gate python3 -m wfcheck --root . finish --task T-001 --author <agent>`
   runs the declared commands, records what happened, and gates the result.
   `--author` names the developer agent that did the work, and is required.

Everything under `.ai-workflow/` is excluded from change-size measurement, so
installing the workflow does not make a project's first task look like a
thousand-line change.

## Fill in the contract before writing code

The gate checks that artifacts agree with each other. It cannot check that the
task is the right task, so the human-shaped part happens first, in this order:

1. `.ai-workflow/product/product-spec.md` — problem, in scope, **out of scope**,
   acceptance criteria. The exclusions are what an agent may not implement even
   when a test would be easier to pass that way.
2. `.ai-workflow/tasks/tasks.json` — one entry per deliverable, with `depends_on`
   and an `acceptance` list of observable results. No `status` field: state is
   derived, and a field an agent can write is not evidence.
3. `.ai-workflow/product/decisions.md` — decisions already made, with reasons, so
   an agent does not relitigate them.

## The loop for each task

Three steps. You do the first; `finish` does the rest.

```sh
# 1. the developer agent implements, and commits the code — a handoff names a commit
git add -A && git commit -m "feat: ..."

# 2. run the evidence, record the handoff, commit it, and gate — one command
PYTHONPATH=.ai-workflow/gate python3 -m wfcheck --root . finish --task T-NNN --author DevT-NNN

# 3. `gate T-NNN PASS` means settled; otherwise read the named problem
```

**Who did the work is part of the record.** A handoff carries `author` and
`author_role`; a review carries `reviewer` and `reviewer_role`. Both are
required, both are role-checked (`developer` to hand off, `reviewer` to
approve), and the gate refuses a review whose reviewer is the handoff's author
(`review-self`). This exists because a purely mechanical gate cannot otherwise
tell a developer's work from the coordinator's: an agent that writes the
implementation itself can produce evidence and a passing gate, and nothing in
the artifacts would say so. Recording the identity does not prove who typed the
code — nothing local can — but it makes the claim explicit, attributable, and
refusable when it contradicts itself.

`finish` is not a shortcut that skips checking: it runs every declared command,
records the real exit codes, writes the handoff, commits the state, then runs the
gate — including re-running the evidence. It refuses exactly the two cases that
used to become silent mistakes:

- **uncommitted work** — a handoff names a commit, and uncommitted content has none;
- **a failing command** — the record is still written (a failure is the most
  important thing to keep), and no handoff is created, so nothing claims success.

Reach for the granular commands only when you need one piece at a time:
`.ai-workflow/bin/test.sh` runs without recording, `wfcheck evidence --task`
records a single kind, `wfcheck handoff` writes a handoff by hand.

**Review is spent in proportion to size.** `WF_REVIEW_MAX` (default 400) is the
number of changed lines that requires a reviewer. Under it, a task settles on
evidence alone — the gate already re-ran the commands. Over it, dispatch the
`reviewer` agent and record its verdict:

```sh
PYTHONPATH=.ai-workflow/gate python3 -m wfcheck --root . review --task T-NNN \
    --verdict approved --reviewer ReviewT-NNN [--finding SEVERITY:ID:SUMMARY ...]
```

`--reviewer` is required and may not match the handoff's `author`: the command
refuses, and the gate refuses with `review-self` if the record was written by
hand.

Size is computed from git over the task's range, excluding `.ai-workflow/`, so it
cannot be declared and cannot be raised with a flag. `status` and `gate` print the
size and the limit, so a skipped review is visible rather than silent.

## Check state, never ask

```sh
PYTHONPATH=.ai-workflow/gate python3 -m wfcheck --root . status   # every task, and its gate
PYTHONPATH=.ai-workflow/gate python3 -m wfcheck --root . ready    # what a developer can start
```

States are derived from artifacts: `todo` (no handoff), `review` (handoff at HEAD,
over the limit, unapproved), `revise` (changes requested, or the commit is behind
HEAD), `merged` (approved, or small enough that its evidence was the check).

Do not ask an agent "is it done?". Read `status`. Do not ask "did tests pass?".
The gate re-runs them.

## Division of labor

`.omp/agents/` ships three role definitions, spawnable with `task`:

- **architect** — turns the spec into tasks with acceptance criteria. No code.
- **developer** — one task end to end, records evidence, writes the handoff.
- **reviewer** — judges one commit against the spec; run only over the size limit.

The main session is the Product Lead: it owns the spec and decides scope. A
developer that reviews its own work is the failure mode this kit exists to prevent,
so never let one agent occupy both roles for the same task.

## Pitfalls that waste an afternoon

- **Recording evidence before the last edit.** Evidence is bound to a tree hash, so
  the edit invalidates it. Re-run after changing code.
- **Trying to supply the command.** `--command` does not exist and `WF_TEST` in the
  environment is ignored; the project's `.ai-workflow/config.sh` is the only authority.
  Do not "fix" that by adding a flag — the caller is the party being checked.
- **Expecting a review for a two-line fix.** Under the limit there is none, by
  design. To require one for everything, set `WF_REVIEW_MAX=0`.
- **Hand-writing `evidence/` or `reviews/`.** The gate re-runs the commands and
  compares the commit; a forged record fails on the run.
- **Dispatching the reviewer too early.** It judges one `reviewed_sha`, and a new
  commit needs a new round. Make the commit final first.
- **Treating the skill directory as a project.** Pass a target directory to
  `install.sh`; it refuses to install into itself.

## When the project already has rules

`AGENTS.md` is written only if absent. If the project has one, merge the three
non-negotiables into it rather than replacing it: the re-run rule, "a review covers
exactly the commit it names", and "task state is derived, never stored". Those are
the ones that change an agent's behavior.

## Uninstall

Delete `.ai-workflow/` and `.omp/agents/`. The workflow keeps no state elsewhere and
writes nothing else.
