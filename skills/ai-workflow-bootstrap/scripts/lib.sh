# shellcheck shell=sh
#
# Shared plumbing for the workflow's entry points.
#
# One rule shapes this file: a script that runs a check also *records* what it
# ran and where. The gate compares that record against git, so an agent cannot
# produce a passing handoff by describing tests it never ran.
#
# Everything here lives under <project>/.ai-workflow/:
#   config.sh   the project's commands (the only file a project edits)
#   bin/        these scripts
#   gate/       the gate itself
#
# WF_TASK  when set, the run is recorded as evidence for that task id.

wf_here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
wf_flow=$(CDPATH= cd -- "$wf_here/.." && pwd)
wf_root=$(CDPATH= cd -- "$wf_flow/.." && pwd)
wf_python=${WF_PYTHON:-python3}

. "$wf_here/../config.sh"

wf_say() {
    printf '%s\n' "$*"
}

# The gate is the workflow's own; it does not require anything from the project
# beyond git and a Python 3 interpreter. --root always precedes the subcommand,
# which is how argparse scopes a global option.
#
# An installed project has it at .ai-workflow/gate/; this repository keeps the
# source at tools/ while developing it, so both locations are accepted.
wf_check_tool() {
    if [ -d "$wf_flow/gate/wfcheck" ]; then
        ( cd "$wf_flow/gate" && PYTHONPATH=. "$wf_python" -m wfcheck --root "$wf_root" "$@" )
    else
        ( cd "$wf_root/tools" && PYTHONPATH=. "$wf_python" -m wfcheck --root "$wf_root" "$@" )
    fi
}

# run_capture <kind>
#
# The CLI owns the run: it reads the command from config.sh, executes it, and
# records the exit code it observed. With WF_TASK unset it records nothing, so a
# mid-work check cannot become a claim.
run_capture() {
    _rc_kind=$1
    if [ -n "${WF_TASK:-}" ]; then
        wf_check_tool evidence --task "$WF_TASK" --kind "$_rc_kind"
    else
        wf_check_tool evidence --kind "$_rc_kind"
    fi
}
