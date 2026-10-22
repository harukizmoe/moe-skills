#!/bin/sh
# End-to-end pass through the real entry point. Records smoke evidence.
set -eu
. "$(dirname -- "$0")/lib.sh"

run_capture smoke
