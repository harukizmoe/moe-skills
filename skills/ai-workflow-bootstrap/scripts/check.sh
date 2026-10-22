#!/bin/sh
# Compile, type-check, lint, format check. Records check evidence when WF_TASK is set.
set -eu
. "$(dirname -- "$0")/lib.sh"

run_capture check
