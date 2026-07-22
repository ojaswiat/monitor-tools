#!/usr/bin/env python3
"""Append one validated operation entry to monitor/logs/log.db.

The schema is locked (see db.py) — no logs/schema.json, no profile-driven
fields. Required shape (operation, tool, summary, status, level, enum values)
is enforced by argparse choices/required plus the DB's own CHECK constraints.
Never hand-edit log.db — always go through this script.

Usage:
  python3 logger.py --project-root <repo> --operation edit-file --tool Edit \\
      --summary "..." --status success [--details "..."] [--files a b] \\
      [--task "..."] [--level INFO] [--branch feat/x] [--set tests=54/54]
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import db
import monitor_lib as mlib


def log_operation(root: Path, *, operation, tool, summary, status,
                  level="INFO", details="", files=None, task="", extra=None,
                  branch=None) -> int:
    # The branch the change was made on. Detected at log time so every entry
    # records where it happened; --branch overrides, "" when not in a repo.
    if branch is None:
        branch = mlib.git_branch(root)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
    entry_id = db.insert_entry(
        root, timestamp=timestamp, level=level, operation=operation,
        tool=tool, summary=summary, status=status, branch=branch, task=task,
        files=files, details=details, extras=extra)
    try:
        import render_logs
        render_logs.render(root)
    except Exception as err:  # noqa: BLE001 — best-effort view refresh
        print(f"warning: could not refresh Logs page: {err}", file=sys.stderr)
    return entry_id


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mlib.add_root_arg(ap)
    ap.add_argument("--operation", required=True)
    ap.add_argument("--tool", required=True)
    ap.add_argument("--summary", required=True)
    ap.add_argument("--status", required=True, choices=db.STATUSES)
    ap.add_argument("--level", default="INFO", choices=db.LEVELS)
    ap.add_argument("--details", default="",
                    help="One labeled point per line (join lines with literal "
                         "\\n, e.g. 'DECISION: ...\\nWHY: ...'); rendered as a "
                         "real list on the Logs page, not a run-on sentence. "
                         "Structuring this well is the caller's job — the "
                         "renderer only decodes what it's given.")
    ap.add_argument("--files", nargs="*", default=None)
    ap.add_argument("--task", default="")
    ap.add_argument("--branch", default=None,
                    help="Branch the change was made on (default: detected).")
    ap.add_argument("--set", action="append", default=[], metavar="key=value",
                    help="Extra field, repeatable. Stored as JSON.")
    args = ap.parse_args()
    root = mlib.resolve_root(args)
    mlib.require_init(root)
    db.init_db(root)
    extra = {}
    for item in args.set:
        if "=" in item:
            k, v = item.split("=", 1)
            extra[k.strip()] = v.strip()
    try:
        log_operation(root, operation=args.operation, tool=args.tool,
                      summary=args.summary, status=args.status,
                      level=args.level, details=args.details,
                      files=args.files, task=args.task, extra=extra,
                      branch=args.branch)
    except sqlite3.IntegrityError as err:
        print(f"log entry rejected: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
