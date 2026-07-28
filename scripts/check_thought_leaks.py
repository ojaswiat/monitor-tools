#!/usr/bin/env python3
"""Grep this repo's shipped documentation for development-history/reasoning-
leakage language, per this repo's own CLAUDE.md rule: no version narration,
no "this was previously X", no meta-commentary about prior approaches in
any user-facing doc. Flags candidates for human/agent review — a hit is
not automatically a real leak (e.g. "previously" can appear in an
unrelated, legitimate sentence), so this never auto-fails a commit; it
prints matches for judgment.

Usage:  python3 scripts/check_thought_leaks.py [--level minimum|standard|high|max]
Exit code: 1 if anything matched (for scripting), 0 if clean.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

TARGET_GLOBS = [
    "plugins/monitor/skills/monitor/SKILL.md",
    "plugins/monitor/commands/*.md",
    "plugins/monitor/README.md",
    "README.md",
    ".claude/skills/*/SKILL.md",
    "CLAUDE.md",
    "AGENTS.md",
]

# Files that quote the banned phrases verbatim in order to STATE the rule
# (the scanner's own skill doc, this repo's CLAUDE.md, and the init
# command that propagates the rule into consumer projects) always match
# themselves, so they are skipped. `.claude/skills/monitor/SKILL.md` is
# this repo's local dogfood copy of
# `plugins/monitor/skills/monitor/SKILL.md` — scanning it reports every
# hit twice, so only the source path is scanned.
EXCLUDED = {
    ".claude/skills/test-thought-leaks/SKILL.md",
    ".claude/skills/monitor/SKILL.md",
    "CLAUDE.md",
    "plugins/monitor/commands/init.md",
}

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

LEVELS = ("minimum", "standard", "high", "max")


def _strip_markdown(s: str) -> str:
    """Strip common markdown syntax for a clean plain-text read: bold/italic
    markers, and [text](url) links reduced to their visible text."""
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    s = re.sub(r"(\*\*|__)(.*?)\1", r"\2", s)
    s = re.sub(r"\*(.*?)\*", r"\1", s)
    s = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"\1", s)
    s = re.sub(r"`([^`]+)`", r"\1", s)
    return s


def _extract_sentence(text: str, line_no: int, matched_text: str) -> str:
    """Return the sentence containing `matched_text` on 1-indexed `line_no`
    within `text`. Splits the line's paragraph (blank-line-delimited block)
    into sentences on '.', '!', '?' followed by whitespace, and returns the
    first sentence whose lowercase form contains the lowercase matched text.
    Falls back to the raw line if no paragraph or sentence boundary is
    found (e.g. a one-line heading with no terminal punctuation)."""
    lines = text.splitlines()
    start = line_no - 1
    para_start = start
    while para_start > 0 and lines[para_start - 1].strip():
        para_start -= 1
    para_end = start
    while para_end < len(lines) - 1 and lines[para_end + 1].strip():
        para_end += 1
    paragraph = " ".join(l.strip() for l in lines[para_start:para_end + 1])
    sentences = re.split(r"(?<=[.!?])\s+", paragraph)
    needle = matched_text.lower()
    for sentence in sentences:
        if needle in sentence.lower():
            return _strip_markdown(sentence).strip()
    return _strip_markdown(lines[start].strip())


def _git_history_for_line(root: Path, path: Path) -> str:
    """`git log -p --follow` for `path`, relative to `root`. Read-only,
    no network. Returns "" if git is unavailable or the file has no
    history (e.g. untracked)."""
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "log", "-p", "--follow", "--", str(path)],
            capture_output=True, text=True, timeout=10)
    except Exception:  # noqa: BLE001 — git missing/unusable, no history to show
        return ""
    return out.stdout if out.returncode == 0 else ""


def find_hits(level: str = "standard") -> list[dict]:
    hits: list[dict] = []
    seen: set[Path] = set()
    for pattern in TARGET_GLOBS:
        for path in sorted(REPO_ROOT.glob(pattern)):
            if path in seen or not path.is_file():
                continue
            rel = path.relative_to(REPO_ROOT).as_posix()
            if rel in EXCLUDED:
                continue
            seen.add(path)
            text = path.read_text(encoding="utf-8", errors="replace")
            file_hits = []
            for i, line in enumerate(text.splitlines(), 1):
                for regex in PATTERNS:
                    m = regex.search(line)
                    if m:
                        file_hits.append((i, m.group(0)))
            if not file_hits:
                continue
            full_file_text = text if level in ("high", "max") else None
            git_history = _git_history_for_line(REPO_ROOT, path) if level == "max" else None
            for line_no, matched_text in file_hits:
                hit = {"path": rel, "line_no": line_no, "matched_text": matched_text}
                if level != "minimum":
                    hit["sentence"] = _extract_sentence(text, line_no, matched_text)
                if full_file_text is not None:
                    hit["full_file_text"] = full_file_text
                if git_history is not None:
                    hit["git_history"] = git_history
                hits.append(hit)
    return hits


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Grep shipped documentation for development-history/"
                     "reasoning-leakage language.")
    ap.add_argument("--level", default="standard", choices=LEVELS,
                    help="How much context to capture per hit: minimum "
                         "(matched line only), standard (+ containing "
                         "sentence, markdown-stripped), high (+ full file "
                         "text), max (+ git log -p history for the file). "
                         "Default: standard.")
    args = ap.parse_args()
    hits = find_hits(args.level)
    if not hits:
        print("clean: no development-history/reasoning-leakage phrases found")
        return 0
    print(f"{len(hits)} candidate(s) found — review each for a real leak vs. a false positive:\n")
    for hit in hits:
        print(f"{hit['path']}:{hit['line_no']}: {hit['matched_text']!r}")
        if "sentence" in hit:
            print(f"  sentence: {hit['sentence']}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
