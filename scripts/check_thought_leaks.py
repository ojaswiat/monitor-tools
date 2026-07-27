#!/usr/bin/env python3
"""Grep this repo's shipped documentation for development-history/reasoning-
leakage language, per this repo's own CLAUDE.md rule: no version narration,
no "this was previously X", no meta-commentary about prior approaches in
any user-facing doc. Flags candidates for human/agent review — a hit is
not automatically a real leak (e.g. "previously" can appear in an
unrelated, legitimate sentence), so this never auto-fails a commit; it
prints matches for judgment.

Usage:  python3 scripts/check_thought_leaks.py
Exit code: 1 if anything matched (for scripting), 0 if clean.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

TARGET_GLOBS = [
    "plugins/monitor/skills/monitor/SKILL.md",
    "plugins/monitor/commands/*.md",
    "README.md",
    ".claude/skills/*/SKILL.md",
    "CLAUDE.md",
    "AGENTS.md",
]

# This scanner's own skill doc quotes the banned phrases verbatim to explain
# what is being looked for, so it always matches itself. Skip it.
EXCLUDED = {".claude/skills/test-thought-leaks/SKILL.md"}

PATTERNS = [
    re.compile(p, re.I) for p in [
        r"\bversion\s+\d+\b",
        r"\bused to\b",
        r"\bpreviously\b",
        r"\bremoved (in|because)\b",
        r"\bearlier version\b",
        r"\bthis was later\b",
        r"\bdeprecated\b",
        r"\bearlier (implementation|approach)\b",
    ]
]


def find_hits() -> list[tuple[Path, int, str]]:
    hits: list[tuple[Path, int, str]] = []
    seen: set[Path] = set()
    for pattern in TARGET_GLOBS:
        for path in sorted(REPO_ROOT.glob(pattern)):
            if path in seen or not path.is_file():
                continue
            if path.relative_to(REPO_ROOT).as_posix() in EXCLUDED:
                continue
            seen.add(path)
            for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                for regex in PATTERNS:
                    m = regex.search(line)
                    if m:
                        hits.append((path.relative_to(REPO_ROOT), i, m.group(0)))
    return hits


def main() -> int:
    hits = find_hits()
    if not hits:
        print("clean: no development-history/reasoning-leakage phrases found")
        return 0
    print(f"{len(hits)} candidate(s) found — review each for a real leak vs. a false positive:\n")
    for path, line_no, text in hits:
        print(f"{path}:{line_no}: {text!r}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
