#!/usr/bin/env python3
"""Append one validated operation entry to monitor/logs/operations.log.

Validates against monitor/logs/schema.json (generated from profile.json),
stamps the entry with the schema version and the current git branch, writes
newest-first, then regenerates the Logs page. Never hand-edit the log — always
go through this script.

Extra profile-added fields are passed with repeatable --set key=value and are
rendered as chips on the Logs page.

Usage:
  python3 logger.py --project-root <repo> --operation edit-file --tool Edit \\
      --summary "..." --status success [--details "..."] [--files a b] \\
      [--task "..."] [--level INFO] [--branch feat/x] [--set tests=54/54]
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import monitor_lib as mlib

SEPARATOR = "=" * 80
STATUSES = ["success", "failure", "partial"]
LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"]


def load_schema(root: Path) -> dict:
    return mlib.load_json(mlib.monitor_dir(root) / "logs" / "schema.json",
                          {"schemaVersion": 1, "required":
                           ["timestamp", "level", "operation", "tool", "summary", "status"],
                           "fields": {}})


def validate(entry: dict, schema: dict) -> None:
    missing = [k for k in schema.get("required", []) if not entry.get(k)]
    if missing:
        raise ValueError(f"missing required fields: {missing}")
    for key, spec in schema.get("fields", {}).items():
        if key in entry and entry[key] not in (None, "", []):
            enum = spec.get("enum")
            if enum and key in entry and str(entry[key]) not in enum:
                raise ValueError(f"{key} must be one of {enum}, got {entry[key]!r}")


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
    schema = load_schema(root)
    # The branch the change was made on. Detected at log time so every entry
    # records where it happened; --branch overrides, "" when not in a repo.
    if branch is None:
        branch = mlib.git_branch(root)
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3],
        "level": level, "operation": operation, "tool": tool,
        "summary": summary, "status": status,
        "schemaVersion": schema.get("schemaVersion", 1),
        "branch": branch,
        "task": task, "details": details, "files": list(files or []),
        "extra": dict(extra or {}),
    }
    validate(entry, schema)
    log_path = mlib.monitor_dir(root) / "logs" / "operations.log"
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
    ap.add_argument("--details", default="")
    ap.add_argument("--files", nargs="*", default=None)
    ap.add_argument("--task", default="")
    ap.add_argument("--branch", default=None,
                    help="Branch the change was made on (default: detected).")
    ap.add_argument("--set", action="append", default=[], metavar="key=value",
                    help="Extra profile field, repeatable.")
    args = ap.parse_args()
    mlib.require_init(mlib.resolve_root(args))
    extra = {}
    for item in args.set:
        if "=" in item:
            k, v = item.split("=", 1)
            extra[k.strip()] = v.strip()
    try:
        log_operation(mlib.resolve_root(args), operation=args.operation,
                      tool=args.tool, summary=args.summary, status=args.status,
                      level=args.level, details=args.details, files=args.files,
                      task=args.task, extra=extra, branch=args.branch)
    except ValueError as err:
        print(f"log entry rejected: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
