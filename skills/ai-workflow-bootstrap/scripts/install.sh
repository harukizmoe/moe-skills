#!/bin/sh
# Install the workflow into a project.
#
# Everything the workflow owns goes under <target>/.ai-workflow/: its commands,
# its entry points, its gate, and its records. Nothing appears at the project
# root, so a project's own scripts/ or config.sh can never collide with, or be
# mistaken for, the workflow's.
#
# It never overwrites an existing file, so re-running after an upgrade is safe
# and a project's own edits survive.
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

flow="$target/.ai-workflow"

# The gate and its entry points are the workflow's actual behavior; keep them in
# sync wholesale. They are inside .ai-workflow/, so syncing cannot touch project
# code.
rm -rf "$flow/gate" "$flow/gate/__pycache__"
mkdir -p "$flow/gate" "$flow/bin"
cp -r "$kit/tools/wfcheck" "$flow/gate/wfcheck"
for name in lib.sh test.sh check.sh smoke-test.sh verify-handoff.sh; do
    cp "$kit/scripts/$name" "$flow/bin/$name"
done
chmod +x "$flow"/bin/*.sh
printf '  synced   .ai-workflow/gate, .ai-workflow/bin\n'

# The one file a project edits.
copy_file "$kit/templates/config.sh" "$flow/config.sh"

copy_file "$kit/templates/AGENTS.md" "$target/AGENTS.md"

for rel in product/product-spec.md product/decisions.md \
           design/design.md design/open-questions.md \
           tasks/tasks.json; do
    copy_file "$kit/templates/.ai-workflow/$rel" "$flow/$rel"
done
# Record directories are empty until the first task, and git does not track empty
# directories: without a placeholder they vanish on clone, and the project looks
# broken for whoever picks it up next.
for dir in handoffs reviews evidence; do
    mkdir -p "$flow/$dir"
    [ -e "$flow/$dir/.gitkeep" ] || : >"$flow/$dir/.gitkeep"
done

copy_file "$kit/templates/.omp/config.yml" "$target/.omp/config.yml"

# Agent roles are part of the workflow contract: a project without them has the
# gates but no division of labor.
for agent in "$kit"/.omp/agents/*.md; do
    copy_file "$agent" "$target/.omp/agents/$(basename "$agent")"
done

# Build junk the gate produces. Committed state under .ai-workflow/ is deliberate:
# the audit trail belongs with the code.
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
printf 'next: edit .ai-workflow/config.sh so WF_TEST / WF_CHECK match this project\n'
