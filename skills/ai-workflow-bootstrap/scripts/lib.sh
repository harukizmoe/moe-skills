# shellcheck shell=sh
#
# Shared plumbing for the workflow scripts.
#
# One rule shapes this file: a script that runs a check also *records* what it
# ran and where. The gates compare that record against git, so an agent cannot
# produce a passing handoff by describing tests it never ran.
#
# WF_TASK  when set, the run is recorded as evidence for that task id.

wf_here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
wf_root=$(CDPATH= cd -- "$wf_here/.." && pwd)
wf_python=${WF_PYTHON:-python3}

. "$wf_here/config.sh"

wf_say() {
    printf '%s\n' "$*"
}

# The gate tool is the kit's own; it does not require anything from the project
# under test beyond git and a Python 3 interpreter. --root always precedes the
# subcommand, which is how argparse scopes a global option.
wf_check_tool() {
    ( cd "$wf_root/tools" \
      && PYTHONPATH=. "$wf_python" -m wfcheck --root "$wf_root" "$@" )
}

# run_capture <kind>
#
# The CLI owns the run: it reads the command from scripts/config.sh, executes it,
# and records the exit code it observed. With WF_TASK unset it records nothing,
# so a mid-work check cannot become a claim.
run_capture() {
    _rc_kind=$1
    if [ -n "${WF_TASK:-}" ]; then
        wf_check_tool evidence --task "$WF_TASK" --kind "$_rc_kind"
    else
        wf_check_tool evidence --kind "$_rc_kind"
    fi
}
