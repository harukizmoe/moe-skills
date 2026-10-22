# shellcheck shell=sh
# What "run the tests" means for THIS repository.
#
# The gates are language-agnostic: they compare git objects and artifacts, never
# source syntax. Only this file knows the language. When the kit is copied into a
# Go, Rust, Node, JVM, or polyglot repository, edit these three values — nothing
# else has to change.
#
# Each value is one shell command line, run from the repository root, quoted
# verbatim into evidence records, so keep it copy-pasteable.
#
# These are plain assignments, not `${VAR:-default}`: the environment must not be
# able to redefine what "verified" means, or `WF_TEST=true wfcheck evidence` would
# pass any gate. To change a command, edit this file; edits are reviewed.
#
# How many changed lines a task may touch before a reviewer must name the commit.
# Under it, re-running the evidence is the whole check: one round costs minutes to
# tens of minutes, and a one-line fix does not need that. Size is read from git,
# so it cannot be declared. 0 means every change needs a review.
WF_REVIEW_MAX="400"

# Empty means "detect", via wf_primary below.

# Left empty on purpose: wf_primary below detects the project's toolchain (Go,
# Cargo, Bun, npm, pytest, Make). Set an explicit value when a project needs a
# command the detection cannot guess, for example a container-wrapped runner.
WF_TEST=""
WF_CHECK=""
WF_SMOKE=""

# Fallback for repositories that have not set the values above: the first
# matching marker wins, so a polyglot repository is served by its primary build
# system. Prints two lines, test then check.
wf_primary() {
    if [ -f go.mod ]; then
        printf '%s\n%s\n' 'go test ./...' 'go vet ./...'
    elif [ -f Cargo.toml ]; then
        printf '%s\n%s\n' 'cargo test' 'cargo clippy --all-targets -- -D warnings'
    elif [ -f bun.lock ] || [ -f bun.lockb ]; then
        printf '%s\n%s\n' 'bun test' 'bun x tsc --noEmit'
    elif [ -f package.json ]; then
        printf '%s\n%s\n' 'npm test --silent' 'npm run --silent lint'
    elif [ -f pyproject.toml ]; then
        printf '%s\n%s\n' "$wf_python -m pytest -q" 'uvx ruff check .'
    elif [ -f Makefile ]; then
        printf '%s\n%s\n' 'make test' 'make check'
    else
        printf '\n\n'
    fi
}

# wf_command <kind> <explicit value>
# Resolves the command for a kind: the explicit value, else detection.
wf_command() {
    _wc_kind=$1
    _wc_value=$2
    if [ -n "$_wc_value" ]; then
        printf '%s' "$_wc_value"
        return
    fi
    case "$_wc_kind" in
        test) wf_primary | sed -n 1p ;;
        check) wf_primary | sed -n 2p ;;
        smoke) printf '%s' '' ;;
        *) printf '%s' '' ;;
    esac
}
