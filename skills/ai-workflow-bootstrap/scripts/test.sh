#!/bin/sh
# Unit tests. Records test evidence when WF_TASK is set.
set -eu
. "$(dirname -- "$0")/lib.sh"

run_capture test
