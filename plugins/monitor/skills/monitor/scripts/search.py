#!/usr/bin/env python3
"""Search monitor/logs/operations.mtr for entries matching a query.

Stdlib-only, plain-text output (no HTML page) — built for an agent to call
and read directly, like grep over the log. Reuses render_logs.parse_log() so
matching stays in sync with how entries are actually parsed.

Usage:
  python3 search.py --project-root <repo> --query "auth bug" \\
      [--branch <name>] [--status success|partial|failure] [--level LEVEL] \\
      [--limit N]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import monitor_lib as mlib
import render_logs


def _haystack(e: dict) -> str:
    parts = [e.get("operation", ""), e.get("tool", ""), e.get("summary", ""),
              e.get("task", ""), e.get("details", ""), e.get("branch", ""),
              e.get("last_commit_hash", "")]
    parts += [f"{k} {v}" for k, v in e.get("extra", {}).items()]
    return " ".join(parts).lower()


def search(root: Path, query: str, *, branch: str | None = None,
           status: str | None = None, level: str | None = None,
           limit: int = 20) -> list[dict]:
    log_path = mlib.monitor_dir(root) / "logs" / "operations.mtr"
    text = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    entries = [e for e in render_logs.parse_log(text) if e.get("fragment") is None]
    q = query.lower()
    matches = []
    for e in entries:
        if q not in _haystack(e):
            continue
        if branch and e.get("branch") != branch:
            continue
        if status and e.get("status") != status:
            continue
        if level and e.get("level") != level:
            continue
        matches.append(e)
        if len(matches) >= limit:
            break
    return matches


def format_match(e: dict) -> str:
    lines = [f"{e['timestamp']} {e['level']} [{e['operation']}] "
              f"({e['tool']}) {e['summary']} -- {e['status']}"]
    if e.get("branch"):
        lines.append(f"  branch:  {e['branch']}")
    if e.get("last_commit_hash"):
        lines.append(f"  commit:  {e['last_commit_hash']}")
    if e.get("task"):
        lines.append(f"  task:    {e['task']}")
    if e.get("files"):
        lines.append(f"  files:   {', '.join(e['files'])}")
    for k, v in e.get("extra", {}).items():
        lines.append(f"  {k}: {v}")
    if e.get("details"):
        lines.append(f"  details: {e['details']}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mlib.add_root_arg(ap)
    ap.add_argument("--query", required=True,
                    help="Case-insensitive substring, matched across operation, "
                         "tool, summary, task, details, branch, commit, and extra fields.")
    ap.add_argument("--branch", default=None)
    ap.add_argument("--status", default=None, choices=("success", "partial", "failure"))
    ap.add_argument("--level", default=None, choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    ap.add_argument("--limit", type=int, default=20)
    args = ap.parse_args()
    root = mlib.resolve_root(args)
    mlib.require_init(root)
    matches = search(root, args.query, branch=args.branch, status=args.status,
                     level=args.level, limit=args.limit)
    if not matches:
        print(f"no matches for {args.query!r}")
        return 0
    print(f"{len(matches)} match(es) for {args.query!r}:\n")
    for e in matches:
        print(format_match(e))
        print("-" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(main())
