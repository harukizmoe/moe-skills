# AGENTS.md

This project runs the AI workflow kit: a task is not done because an agent says
so, it is done when `.ai-workflow/bin/verify-handoff.sh` agrees.

Replace this file's body with the project's own rules. Keep only what changes an
agent's decisions; a longer file is not a better one.

## Commands

```sh
.ai-workflow/bin/test.sh                    # test suite        (WF_TASK=<id> records evidence)
.ai-workflow/bin/check.sh                   # compile/lint      (WF_TASK=<id> records evidence)
.ai-workflow/bin/smoke-test.sh              # end-to-end        (WF_TASK=<id> records evidence)
.ai-workflow/bin/verify-handoff.sh <TASK>   # merge gate: artifacts + re-execution
```

Command definitions live in `.ai-workflow/config.sh`. Nothing else knows the language.

## Authority

`.ai-workflow/` is the only authoritative state. Chat history and agent memory
are not.

| Path | Contents |
| --- | --- |
| `product/product-spec.md` | scope, exclusions, acceptance criteria |
| `product/decisions.md` | confirmed decisions and reasons |
| `design/design.md` | technical plan (complex tasks only) |
| `design/open-questions.md` | questions that need a human |
| `tasks/tasks.json` | tasks, dependencies, acceptance (state is derived) |
| `handoffs/<TASK>.json` | the developer's claim: commit, tree, evidence paths |
| `reviews/<TASK>-r<N>.json` | reviewer verdicts, one per round |
| `evidence/<TASK>-<KIND>.json` | what actually ran, and on which content |

## Who does what

The main session coordinates: it owns the spec, the scope, and the task graph, and
it decides when a task is settled. It does not write product code — a developer
agent does, one task per spawn — and it never approves work it implemented itself,
which the gate refuses as `review-self`.

| Role | Who | Does |
| --- | --- | --- |
| coordinator | main session | spec, decisions, tasks; dispatch; run `finish` and reviews |
| developer | `.omp/agents/developer.md` | one task end to end; sign the handoff with `--author` |
| architect | `.omp/agents/architect.md` | turn an approved spec into design and tasks |
| reviewer | `.omp/agents/reviewer.md` | judge one commit with `--reviewer` |

## Non-negotiables

1. `evidence/` is written only by the scripts. Never hand-write it.
2. The commands come from `.ai-workflow/config.sh` alone — not from a flag, not from
   the environment. Editing that file is the only way to change what "verified"
   means, and edits there are reviewed.
3. A handoff is a claim, and it names its `author`. `verify-handoff.sh` re-runs its
   commands and refuses on mismatch; there is no flag to skip the re-run.
4. A review covers exactly the commit it names, and it names its `reviewer`. New
   commit, new review. The reviewer may not be the handoff's author.
5. Passing tests does not mean the requirement is met; acceptance comes from the
   product spec, not from what the system returned.
6. A task's state is derived from its artifacts (`todo` / `review` / `revise` /
   `merged`). There is no status field to write, so do not look for one.
7. A review is required only over `WF_REVIEW_MAX` changed lines. Size comes from
   git, so it cannot be declared or raised with a flag; under the limit, re-running
   the evidence is the whole check. Do not add a review step "to be safe".
8. Never widen the approved scope to make a test pass.
