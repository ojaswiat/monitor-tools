#!/usr/bin/env python3
"""Append one validated operation entry to monitor/logs/operations.mtr.

The schema is LOCKED in code (REQUIRED/LEVELS/STATUSES below), identical
across every project. Stamps the entry with the current branch, writes
newest-first, then regenerates the Logs page. Never hand-edit the log —
always go through this script.

Usage:
  python3 logger.py --project-root <repo> --operation edit-file --tool Edit \\
      --summary "..." --status success [--details "..."] [--files a b] \\
      [--task "..."] [--level INFO] [--branch feat/x] [--set tests=54/54]
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

# Strips ASCII control bytes (NUL..BS, VT, FF, SO..US, DEL) — e.g. the raw
# ANSI escape codes a backtick-quoted example command can splice into a field
# via accidental shell command substitution. Tab is left alone; real newlines
# are handled separately in sanitize() since they'd break the block format.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize(value: str) -> str:
    """Every field is sanitized before it ever reaches operations.mtr: strip
    control characters, flatten real newlines to spaces (the log is
    block/line-based — a raw newline inside a field would corrupt parsing),
    and trim. This runs on every entry regardless of caller; there is no way
    to write an unsanitized field to the log."""
    if value is None:
        return value
    value = str(value).replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    return _CONTROL_CHARS.sub("", value).strip()


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
    if entry.get("task"):
        lines.append(f"task:    {entry['task']}")
    if entry.get("files"):
        lines.append(f"files:   {', '.join(entry['files'])}")
    for k, v in entry.get("extra", {}).items():
        lines.append(f"{k}: {v}")
    if entry.get("details"):
        lines.append(f"details: {entry['details']}")
    return "\n".join(lines)


def log_operation(root: Path, *, operation, tool, summary, status,
                  level="INFO", details="", files=None, task="", extra=None,
                  branch=None) -> None:
    # The branch the change was made on. Detected at log time so every entry
    # records where it happened; --branch overrides, "" when not in a repo.
    if branch is None:
        branch = mlib.git_branch(root)
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3],
        "level": sanitize(level), "operation": sanitize(operation),
        "tool": sanitize(tool), "summary": sanitize(summary),
        "status": sanitize(status), "branch": sanitize(branch),
        "task": sanitize(task), "details": sanitize(details),
        "files": [sanitize(f) for f in (files or [])],
        "extra": {sanitize(k): sanitize(v) for k, v in (extra or {}).items()},
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
    except Exception as err:  # noqa: BLE001 — best-effort view refresh
        print(f"warning: could not refresh Logs page: {err}", file=sys.stderr)


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
    ap.add_argument("--task", default="")
    ap.add_argument("--branch", default=None,
                    help="Branch the change was made on (default: detected).")
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
                      task=args.task, extra=extra, branch=args.branch)
    except ValueError as err:
        print(f"log entry rejected: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
