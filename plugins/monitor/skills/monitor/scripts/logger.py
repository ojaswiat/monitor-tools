#!/usr/bin/env python3
"""Append one validated operation entry to monitor/logs/operations.mtr.

The schema is LOCKED in code (REQUIRED/LEVELS/STATUSES below), identical
across every project. Stamps the entry with the current branch, writes
newest-first, then regenerates the Logs page. Never hand-edit the log —
always go through this script.

Usage:
  python3 logger.py --project-root <repo> --operation edit-file --tool Edit \\
      --summary "..." --status success [--details "..."] [--files a b] \\
      [--task-id "..."] [--level INFO] [--branch feat/x] [--set tests=54/54] \\
      [--last-commit-hash <sha>]
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

import monitor_lib as mlib

SEPARATOR = "=" * 80
STATUSES = ("success", "partial", "failure")
LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")
REQUIRED = ("timestamp", "level", "operation", "tool", "summary", "status")


def validate(entry: dict) -> None:
    missing = [k for k in REQUIRED if not entry.get(k)]
    if missing:
        raise ValueError(f"missing required fields: {missing}")
    if entry["level"] not in LEVELS:
        raise ValueError(f"level must be one of {LEVELS}, got {entry['level']!r}")
    if entry["status"] not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}, got {entry['status']!r}")


def render_entry(entry: dict) -> str:
    lines = [
        f"{entry['timestamp']} {entry['level']} [{entry['operation']}] "
        f"({entry['tool']}) {entry['summary']} -- {entry['status']}"
    ]
    if entry.get("branch"):
        lines.append(f"branch:  {entry['branch']}")
    if entry.get("last_commit_hash"):
        lines.append(f"last_commit_hash: {entry['last_commit_hash']}")
    if entry.get("task_id"):
        lines.append(f"task_id: {entry['task_id']}")
    if entry.get("files"):
        lines.append(f"files:   {', '.join(entry['files'])}")
    for k, v in entry.get("extra", {}).items():
        lines.append(f"{k}: {v}")
    if entry.get("details"):
        lines.append(f"details: {entry['details']}")
    return "\n".join(lines)


def log_operation(root: Path, *, operation, tool, summary, status,
                  level="INFO", details="", files=None, task_id=None, extra=None,
                  branch=None, last_commit_hash=None) -> None:
                                                                            
                                                                           
    if branch is None:
        branch = mlib.git_branch(root)
    if last_commit_hash is None:
        last_commit_hash = mlib.git_last_commit(root)
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3],
        "level": mlib.sanitize(level), "operation": mlib.sanitize(operation),
        "tool": mlib.sanitize(tool), "summary": mlib.sanitize(summary),
        "status": mlib.sanitize(status), "branch": mlib.sanitize(branch),
        "task_id": mlib.sanitize(task_id) if task_id else "",
        "details": mlib.sanitize(details),
        "files": [mlib.sanitize(f) for f in (files or [])],
        "extra": {mlib.sanitize(k): mlib.sanitize(v) for k, v in (extra or {}).items()},
        "last_commit_hash": mlib.sanitize(last_commit_hash),
    }
    validate(entry)
    log_path = mlib.monitor_dir(root) / "logs" / "operations.mtr"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    block = render_entry(entry) + "\n" + SEPARATOR + "\n"
    previous = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    log_path.write_text(block + previous, encoding="utf-8")
    try:
        import render_logs
        render_logs.render(root)
    except Exception as err:                                           
        print(f"warning: could not refresh Logs page: {err}", file=sys.stderr)
    try:
        import render_report
        render_report.refresh_dashboard(root)
    except Exception as err:                                           
        print(f"warning: could not refresh Dashboard: {err}", file=sys.stderr)
    try:
        import pending
        if entry.get("last_commit_hash"):
            pending.clear_log(root, entry["last_commit_hash"])
    except Exception as err:                                                   
        print(f"warning: could not update pending state: {err}", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mlib.add_root_arg(ap)
    ap.add_argument("--operation", required=True)
    ap.add_argument("--tool", required=True)
    ap.add_argument("--summary", required=True)
    ap.add_argument("--status", required=True, choices=STATUSES)
    ap.add_argument("--level", default="INFO", choices=LEVELS)
    ap.add_argument("--details", default="",
                    help="One labeled point per line (join lines with literal "
                         "\\n, e.g. 'DECISION: ...\\nWHY: ...'); rendered as a "
                         "real list on the Logs page, not a run-on sentence. "
                         "Structuring this well is the caller's job — the "
                         "renderer only decodes what it's given.")
    ap.add_argument("--files", nargs="*", default=None)
    ap.add_argument("--task-id", dest="task_id", default=None,
                    help="Optional foreign key into monitor/tasks/tasks.mtr — "
                         "the task this log entry happened during.")
    ap.add_argument("--branch", default=None,
                    help="Branch the change was made on (default: detected).")
    ap.add_argument("--last-commit-hash", default=None,
                    help="Commit sha this entry is about (default: current "
                         "HEAD). Pass the entry's own sha when working "
                         "through several pending_logs entries, so each log "
                         "clears its own pending entry rather than HEAD's.")
    ap.add_argument("--set", action="append", default=[], metavar="key=value",
                    help="Extra profile field, repeatable.")
    args = ap.parse_args()
    root = mlib.resolve_root(args)
    mlib.require_init(root)
    extra = {}
    for item in args.set:
        if "=" in item:
            k, v = item.split("=", 1)
            extra[k.strip()] = v.strip()
    try:
        log_operation(root, operation=args.operation, tool=args.tool,
                      summary=args.summary, status=args.status,
                      level=args.level, details=args.details, files=args.files,
                      task_id=args.task_id, extra=extra, branch=args.branch,
                      last_commit_hash=args.last_commit_hash)
    except ValueError as err:
        print(f"log entry rejected: {err}", file=sys.stderr)
        return 1
    print(f"logged: {args.operation} ({args.status})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
