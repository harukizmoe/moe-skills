# Behavior test cases

Manual behavior matrix for `ai-workflow-bootstrap`. CI validates structure only
(frontmatter, executability, referenced paths); these cases are what a maintainer
walks through before tagging a release.

Run them in a throwaway directory. Every case starts from an empty directory
unless stated otherwise. Substitute the skill's own path for `$SKILL`.

## CASE: bootstrap from nothing

Given:
  an empty directory, no git repository

Steps:
  sh "$SKILL/scripts/install.sh" .
  git init -b main
  git add -A && git commit -m "chore: initialise workflow"
  PYTHONPATH=.ai-workflow/gate python3 -m wfcheck --root . status

Expected:
  `.ai-workflow/{gate,bin,config.sh,tasks,handoffs,reviews,evidence,product,design}`
  exist.
  Nothing appears at the project root except `.ai-workflow/`, `.omp/`, `AGENTS.md`,
  `.gitignore` — specifically no `tools/` and no `scripts/`.
  `status` prints one line for the placeholder task and exits 0.

## CASE: the one-command loop

Given:
  a bootstrapped Go project with `go.mod` and a passing suite

Steps:
  edit the code
  git add -A && git commit -m "feat: ..."
  PYTHONPATH=.ai-workflow/gate python3 -m wfcheck --root . finish --task T-001
  PYTHONPATH=.ai-workflow/gate python3 -m wfcheck --root . status

Expected:
  `finish` prints `gate T-001 PASS`.
  `status` shows the task `merged`.
  `git status --porcelain` is empty afterwards: `finish` committed the state.

## CASE: a dirty tree is refused

Given:
  a bootstrapped project with a modification that is not committed

Steps:
  PYTHONPATH=.ai-workflow/gate python3 -m wfcheck --root . finish --task T-001

Expected:
  exits 1 with `uncommitted changes`. A handoff names a commit, and uncommitted
  content has none.

## CASE: a failing command keeps its record and writes no handoff

Given:
  a bootstrapped project whose `WF_TEST` exits 1

Steps:
  PYTHONPATH=.ai-workflow/gate python3 -m wfcheck --root . finish --task T-001

Expected:
  exits 1 naming the failed kind.
  `.ai-workflow/evidence/T-001-test.json` exists with `exit_code: 1`.
  `.ai-workflow/handoffs/T-001.json` does **not** exist: nothing claims success.

## CASE: a hand-written command is refused

Given:
  a project whose evidence record names a command the project does not declare

Steps:
  edit the record so `command` reads `true`
  PYTHONPATH=.ai-workflow/gate python3 -m wfcheck --root . gate --task T-001

Expected:
  exits 1 with `evidence-command`. The flag `--command` does not exist, and
  exporting `WF_TEST=true` is ignored.

## CASE: approval does not carry to a new commit

Given:
  a project where a task was approved at commit A

Steps:
  make a further commit B
  PYTHONPATH=.ai-workflow/gate python3 -m wfcheck --root . gate --task T-001

Expected:
  exits 1 with `review-stale` naming A and the handoff's commit.

## CASE: review is spent in proportion to size

Given:
  `WF_REVIEW_MAX="10"` in `.ai-workflow/config.sh`

Steps:
  a) change two lines, commit, `finish`
  b) change two hundred lines, commit, `finish`

Expected:
  a) passes with no review; `change_size` reads `2 lines, no review under 10`
  b) refused with `review-missing`; `change_size` reads `200 lines, review
     required over 10`

## CASE: the size cannot be hidden by commit layout

Given:
  `WF_REVIEW_MAX="10"` and a change of two hundred lines

Steps:
  commit the code
  commit the evidence separately
  commit the handoff separately
  gate the task

Expected:
  still refused with `review-missing`: the range walks back over the state-only
  commits and inherits the size of the work they describe.

## CASE: a state-only commit after the handoff is not new work

Given:
  a task whose handoff was recorded against its own commit

Steps:
  `git commit` the `.ai-workflow/` changes
  gate the task

Expected:
  passes. `head-advanced` does not fire: trailing state commits are bookkeeping.

## CASE: an existing project is never clobbered

Given:
  a project with its own `scripts/test.sh` and its own `config.sh` at the root

Steps:
  sh "$SKILL/scripts/install.sh" .
  sh "$SKILL/scripts/install.sh" .          # second run

Expected:
  both report the existing files as left alone; the project's own `scripts/test.sh`
  is untouched.
  The second run writes 0 files.

## CASE: record directories survive a clone

Given:
  a freshly bootstrapped project with no tasks yet

Steps:
  git add -A && git commit -m "init"
  git clone <project> /tmp/copy
  ls /tmp/copy/.ai-workflow/evidence /tmp/copy/.ai-workflow/handoffs /tmp/copy/.ai-workflow/reviews

Expected:
  all three directories exist and contain `.gitkeep`.
  Git does not track empty directories, so without the placeholder a fresh
  checkout looks like a broken install.

## CASE: language detection

Given:
  an empty directory containing only `go.mod` and a Go package

Steps:
  install, leave `WF_TEST` and `WF_CHECK` empty in `.ai-workflow/config.sh`
  PYTHONPATH=.ai-workflow/gate python3 -m wfcheck --root . finish --task T-001

Expected:
  runs `go test ./...` then `go vet ./...`, recording both.
  A directory with no recognisable toolchain refuses rather than passing.

## CASE: a broken review file is reported, not skipped

Given:
  a project with `.ai-workflow/reviews/T-001-r2.json` containing `{broken`

Steps:
  PYTHONPATH=.ai-workflow/gate python3 -m wfcheck --root . status

Expected:
  exits 1 and names the invalid JSON. Silently ignoring an unreadable round would
  report the previous round's approval as if it were the latest.
