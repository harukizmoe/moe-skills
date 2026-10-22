#!/bin/sh
# Install the workflow kit into a project.
#
# Copies only what a project needs to run the gates: the scripts, the gate tool,
# and (unless the project already has them) the AGENTS.md and .ai-workflow
# skeleton. It never overwrites an existing file, so re-running after an upgrade
# is safe and a project's own edits survive.
#
# Usage: install.sh <target-project-dir> [--force]
set -eu

kit=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
target=${1:-}
force=no
[ "${2:-}" = "--force" ] && force=yes

if [ -z "$target" ]; then
    printf 'usage: install.sh <target-project-dir> [--force]\n' >&2
    exit 2
fi
mkdir -p "$target"
target=$(CDPATH= cd -- "$target" && pwd)

if [ "$kit" = "$target" ]; then
    printf 'refusing to install the kit into itself\n' >&2
    exit 2
fi

copied=0
skipped=0

# copy_file <source> <destination>
copy_file() {
    src=$1
    dst=$2
    if [ -e "$dst" ] && [ "$force" != yes ]; then
        printf '  exists   %s\n' "${dst#"$target"/}"
        skipped=$((skipped + 1))
        return
    fi
    mkdir -p "$(dirname -- "$dst")"
    cp "$src" "$dst"
    printf '  wrote    %s\n' "${dst#"$target"/}"
    copied=$((copied + 1))
}

# The tool and the scripts are the kit's actual behavior; keep them in sync
# wholesale.
rm -rf "$target/tools/wfcheck" "$target/tools/__pycache__"
mkdir -p "$target/tools" "$target/scripts"
cp -r "$kit/tools/wfcheck" "$target/tools/wfcheck"
# `lib.sh`, the runner scripts, and the installer are fixed plumbing; only
# `config.sh` differs per project, and an existing one is never overwritten.
for name in lib.sh test.sh check.sh smoke-test.sh verify-handoff.sh install.sh; do
    cp "$kit/scripts/$name" "$target/scripts/$name"
done
copy_file "$kit/templates/config.sh" "$target/scripts/config.sh"
chmod +x "$target"/scripts/*.sh
printf '  synced   tools/wfcheck, scripts/\n'

copy_file "$kit/templates/AGENTS.md" "$target/AGENTS.md"

for rel in product/product-spec.md product/decisions.md \
           design/design.md design/open-questions.md \
           tasks/tasks.json; do
    copy_file "$kit/templates/.ai-workflow/$rel" "$target/.ai-workflow/$rel"
done
for dir in handoffs reviews evidence; do
    mkdir -p "$target/.ai-workflow/$dir"
done

copy_file "$kit/templates/.omp/config.yml" "$target/.omp/config.yml"

# Agent roles are part of the workflow contract: a project without them has the
# gates but no division of labor.
for agent in "$kit"/.omp/agents/*.md; do
    copy_file "$agent" "$target/.omp/agents/$(basename "$agent")"
done

# Build junk the gate tool produces. Committed state under .ai-workflow/ is
# deliberate: the audit trail belongs with the code.
if [ ! -f "$target/.gitignore" ]; then
    printf '__pycache__/\n*.pyc\n.ruff_cache/\n' > "$target/.gitignore"
    printf '  wrote    .gitignore\n'
else
    for pattern in __pycache__/ '*.pyc' .ruff_cache/; do
        grep -qxF "$pattern" "$target/.gitignore" 2>/dev/null \
            || printf '%s\n' "$pattern" >> "$target/.gitignore"
    done
    printf '  updated  .gitignore (build junk only)\n'
fi

printf '\n%d written, %d left alone\n' "$copied" "$skipped"
printf 'next: edit scripts/config.sh so WF_TEST / WF_CHECK match this project\n'
