#!/usr/bin/env bash
# Fallback installer for the `monitor` plugin — copies the skill + commands into a
# target project's .claude/ without a marketplace. Use this when you don't want to
# register a Claude Code marketplace (see README for the /plugin install path).
#
# Usage:  ./install-monitor.sh <target-project-dir> [--force]
#
# It installs TWO things into <target>/.claude/ :
#   skills/monitor/        (SKILL.md + engine scripts + assets)
#   commands/monitor.md    and  commands/monitor/   (the /monitor:* slash commands)
# It NEVER touches the target's top-level monitor/ data folder — that is generated
# by running /monitor:init inside the target project afterwards.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN="$SCRIPT_DIR/plugins/monitor"

TARGET="${1:-}"
FORCE="${2:-}"
if [ -z "$TARGET" ]; then
  echo "usage: $0 <target-project-dir> [--force]" >&2
  exit 2
fi
if [ ! -d "$TARGET" ]; then
  echo "error: target project dir not found: $TARGET" >&2
  exit 1
fi
if [ ! -d "$PLUGIN/skills/monitor" ] || [ ! -f "$PLUGIN/commands/monitor.md" ]; then
  echo "error: plugin payload missing under $PLUGIN (run from the marketplace root)" >&2
  exit 1
fi

DEST_SKILL="$TARGET/.claude/skills/monitor"
DEST_CMD="$TARGET/.claude/commands"

if { [ -e "$DEST_SKILL" ] || [ -e "$DEST_CMD/monitor.md" ] || [ -e "$DEST_CMD/monitor" ]; } \
   && [ "$FORCE" != "--force" ]; then
  echo "error: monitor is already installed in $TARGET/.claude (skill and/or commands present)." >&2
  echo "       re-run with --force to overwrite the ENGINE + COMMANDS (your monitor/ DATA is never touched)." >&2
  exit 1
fi

mkdir -p "$TARGET/.claude/skills" "$DEST_CMD"
rm -rf "$DEST_SKILL" "$DEST_CMD/monitor"
cp -R "$PLUGIN/skills/monitor" "$DEST_SKILL"
rm -rf "$DEST_SKILL/scripts/__pycache__"
cp "$PLUGIN/commands/monitor.md" "$DEST_CMD/monitor.md"
cp -R "$PLUGIN/commands/monitor" "$DEST_CMD/monitor"

echo "✓ installed monitor into $TARGET/.claude/"
echo "    skills/monitor/           (engine + SKILL.md + assets)"
echo "    commands/monitor.md + commands/monitor/   (/monitor:* commands)"
echo
echo "Next: open the target project in Claude Code and run  /monitor:init"
echo "      (that generates the project-local monitor/ Dashboard, Reports, and Logs)."
