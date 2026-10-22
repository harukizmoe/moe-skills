#!/bin/sh
# Gate one task, re-running its evidence.
#
# Merging is the only step that cannot be undone by a later agent, so this checks
# the artifacts against git and then re-runs what they claim ran.
#
# Usage: scripts/verify-handoff.sh TASK_ID
set -eu
. "$(dirname -- "$0")/lib.sh"

task=${1:-}
if [ -z "$task" ] || [ "${task#-}" != "$task" ]; then
    wf_say "usage: scripts/verify-handoff.sh TASK_ID"
    exit 2
fi

wf_check_tool gate --task "$task"
