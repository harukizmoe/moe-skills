# Behavior test cases

Manual behavior matrix for `ai-workflow-bootstrap`. CI validates structure only
(frontmatter, executability, referenced paths); these cases are what a maintainer
walks through before tagging a release.

Run them in a throwaway directory. Every case starts from an empty directory
unless stated otherwise.

## CASE: bootstrapped project can be gated

Given:
  an empty directory
  git configured with a user

Steps:
  sh scripts/install.sh .
  git init -b main
  edit scripts/config.sh so WF_TEST and WF_CHECK are real commands
  git add -A && git commit -m "chore: initialise workflow"
  WF_TASK=T-001 sh scripts/test.sh
  WF_TASK=T-001 sh scripts/check.sh
  git add -A && git commit -m "feat: first task"
  python3 -m wfcheck --task T-001 --evidence .ai-workflow/evidence/T-001-test.json \
      .ai-workflow/evidence/T-001-check.json
  git add -A && git commit -m "chore: handoff"
  sh scripts/verify-handoff.sh T-001

Expected:
  every step exits 0; the last prints `gate T-001 PASS`.
  `python3 -m wfcheck --root . status` shows `T-001  merged`.

## CASE: a false claim is refused

Given:
  a project bootstrapped as above, with a test suite that currently fails

Steps:
  WF_TASK=T-001 sh scripts/test.sh        # records exit 1
  git add -A && git commit -m wip
  python3 -m wfcheck --task T-001 --evidence <both records>
  sh scripts/verify-handoff.sh T-001

Expected:
  the gate exits 1 and lists `evidence-failed` and `evidence-missing`.
  It never prints `PASS`.

## CASE: a hand-written command is refused

Given:
  a project whose evidence records a command the project does not declare

Steps:
  edit .ai-workflow/evidence/T-001-test.json so `command` reads `true`
  sh scripts/verify-handoff.sh T-001

Expected:
  exits 1 with `evidence-command`. The flag `--command` does not exist, and
  exporting `WF_TEST=true` is ignored.

## CASE: approval does not carry to a new commit

Given:
  a project where T-001 was approved at commit A

Steps:
  make a further commit B
  sh scripts/verify-handoff.sh T-001

Expected:
  exits 1 with `review-stale` naming A and the handoff's commit.

## CASE: review is spent in proportion to size

Given:
  a project with `WF_REVIEW_MAX="10"`

Steps:
  a) change two lines, record evidence, hand off, gate
  b) change two hundred lines, record evidence, hand off, gate

Expected:
  a) passes with no review; `change_size` reads `2 lines, no review under 10`
  b) refused with `review-missing`; `change_size` reads `200 lines, review
     required over 10`

## CASE: the size cannot be hidden by commit layout

Given:
  a project with `WF_REVIEW_MAX="10"` and a change of two hundred lines

Steps:
  commit the code
  commit the evidence separately
  commit the handoff separately
  sh scripts/verify-handoff.sh T-001

Expected:
  still refused with `review-missing`: the range walks back over the state-only
  commits and inherits the size of the work they describe.

## CASE: an existing project is never clobbered

Given:
  a project with its own AGENTS.md and its own scripts/config.sh

Steps:
  sh scripts/install.sh .
  sh scripts/install.sh .          # second run

Expected:
  both report the existing files as left alone; neither is overwritten.
  The second run changes no file.

## CASE: language detection

Given:
  an empty directory containing only `go.mod` and a Go package

Steps:
  sh scripts/install.sh .
  leave WF_TEST and WF_CHECK empty in scripts/config.sh
  WF_TASK=T-001 sh scripts/test.sh
  WF_TASK=T-001 sh scripts/check.sh

Expected:
  runs `go test ./...` then `go vet ./...`, recording both.
  A directory with no recognisable toolchain refuses rather than passing.

## CASE: not inside a repository yet

Given:
  an empty directory with no `git init`

Steps:
  sh scripts/install.sh .

Expected:
  installation succeeds; the gate reports a missing `tasks.json` rather than a
  traceback. Committing the skeleton first is required before any gate can pass.
