#!/usr/bin/env python3
"""PostToolUse hook: after any Bash command containing `git push`, if the
current branch is main, refresh this repo's own plugin marketplace cache
so a stale local cache never silently diverges from what was just pushed.

Dev-only tooling for this repo's own workflow -- never shipped to Guest
projects, not part of the monitor plugin.

Usage (wired via .claude/settings.json PostToolUse, matcher "Bash|Write"):
  echo '<hook JSON>' | python3 scripts/post_push_hook.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MARKETPLACE_NAME = "monitor-tools"
_MAIN_TARGET_RE = re.compile(r"\bmain\b")


def _current_branch() -> str:
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else ""


def _pushes_main(command: str) -> bool:
    """True if this push command targets main -- either explicitly named
    (`git push origin main`, works regardless of the currently checked-out
    branch) or implicit (a bare `git push` while main is checked out)."""
    if _MAIN_TARGET_RE.search(command):
        return True
    return _current_branch() == "main"


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command", "") or ""
    if "git push" not in command:
        return 0
    if not _pushes_main(command):
        return 0
    result = subprocess.run(
        ["claude", "plugin", "marketplace", "update", MARKETPLACE_NAME],
        capture_output=True, text=True)
    if result.returncode == 0:
        print(f"[post-push] refreshed {MARKETPLACE_NAME} marketplace cache after push to main")
    else:
        print(f"[post-push] marketplace update failed: {result.stderr.strip()}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
