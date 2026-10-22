# AGENTS.md

This project runs the AI workflow kit: a task is not done because an agent says
so, it is done when `scripts/verify-handoff.sh` agrees.

Replace this file's body with the project's own rules. Keep only what changes an
agent's decisions; a longer file is not a better one.

## Commands

```sh
scripts/test.sh                    # test suite        (WF_TASK=<id> records evidence)
scripts/check.sh                   # compile/lint      (WF_TASK=<id> records evidence)
scripts/smoke-test.sh              # end-to-end        (WF_TASK=<id> records evidence)
scripts/verify-handoff.sh <TASK>   # merge gate: artifacts + re-execution
```

Command definitions live in `scripts/config.sh`. Nothing else knows the language.

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

## Non-negotiables

1. `evidence/` is written only by the scripts. Never hand-write it.
2. The commands come from `scripts/config.sh` alone — not from a flag, not from
   the environment. Editing that file is the only way to change what "verified"
   means, and edits there are reviewed.
3. A handoff is a claim. `verify-handoff.sh` re-runs its commands and refuses on
   mismatch; there is no flag to skip the re-run.
4. A review covers exactly the commit it names. New commit, new review.
5. Passing tests does not mean the requirement is met; acceptance comes from the
   product spec, not from what the system returned.
6. A task's state is derived from its artifacts (`todo` / `review` / `revise` /
   `merged`). There is no status field to write, so do not look for one.
7. A review is required only over `WF_REVIEW_MAX` changed lines. Size comes from
   git, so it cannot be declared or raised with a flag; under the limit, re-running
   the evidence is the whole check. Do not add a review step "to be safe".
8. Never widen the approved scope to make a test pass.
