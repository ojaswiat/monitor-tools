#!/usr/bin/env python3
"""Append one lifecycle event to monitor/tasks/tasks.mtr (task-start,
task-update, or task-close), then regenerate monitor/tasks/*.html.

A task is a separate tracked entity from the operations log — it is not a
free-text label on a log entry. Metrics (tokens/credits/cost/skills_used/
tools_called) are self-reported by the calling agent via CLI flags; the
engine has no way to introspect the real session, so this is the same trust
model logger.py's --details already uses.

Usage:
  python3 tasks.py start --title "..." [--status open] [--summary "..."] \\
      [--tokens N] [--credits N] [--cost N] [--skills-used a b] \\
      [--tools-called a b] [--details "..."] [--branch feat/x]
  python3 tasks.py update --task-id <id> --status in_progress --summary "..." [metrics...]
  python3 tasks.py close --task-id <id> --status success --summary "..." [metrics...]
"""

from __future__ import annotations

import argparse
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path

import monitor_lib as mlib

SEPARATOR = "=" * 80
LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")
NONTERMINAL = ("open", "in_progress", "needs_approval", "needs_retry", "blocked")
TERMINAL = ("success", "failed", "cancelled")
STATUSES = NONTERMINAL + TERMINAL
REQUIRED = ("timestamp", "level", "event", "task_id", "summary", "status")

_TASK_ID_LINE = re.compile(r"^task_id: (\S+)$", re.M)


def _tasks_path(root: Path) -> Path:
    return mlib.monitor_dir(root) / "tasks" / "tasks.mtr"


def _existing_task_ids(root: Path) -> set[str]:
    path = _tasks_path(root)
    if not path.exists():
        return set()
    return set(_TASK_ID_LINE.findall(path.read_text(encoding="utf-8")))


def new_task_id(root: Path) -> str:
    existing = _existing_task_ids(root)
    while True:
        candidate = uuid.uuid4().hex[:8]
        if candidate not in existing:
            return candidate


def validate(entry: dict) -> None:
    missing = [k for k in REQUIRED if not entry.get(k)]
    if missing:
        raise ValueError(f"missing required fields: {missing}")
    if entry["level"] not in LEVELS:
        raise ValueError(f"level must be one of {LEVELS}, got {entry['level']!r}")
    if entry["status"] not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}, got {entry['status']!r}")
    if entry["event"] == "task-close":
        if entry["status"] not in TERMINAL:
            raise ValueError(
                f"task-close requires a terminal status {TERMINAL}, got {entry['status']!r}")
    else:
        if entry["status"] not in NONTERMINAL:
            raise ValueError(
                f"{entry['event']} requires a non-terminal status {NONTERMINAL}, "
                f"got {entry['status']!r}")


def render_entry(entry: dict) -> str:
    lines = [
        f"{entry['timestamp']} {entry['level']} [{entry['event']}] "
        f"({entry['task_id']}) {entry['summary']} -- {entry['status']}",
        f"task_id: {entry['task_id']}",
    ]
    if entry.get("title"):
        lines.append(f"title:   {entry['title']}")
    if entry.get("branch"):
        lines.append(f"branch:  {entry['branch']}")
    if entry.get("last_commit_hash"):
        lines.append(f"last_commit_hash: {entry['last_commit_hash']}")
    if entry.get("tokens") is not None:
        lines.append(f"tokens: {entry['tokens']}")
    if entry.get("credits") is not None:
        lines.append(f"credits: {entry['credits']}")
    if entry.get("cost") is not None:
        lines.append(f"cost: {entry['cost']}")
    if entry.get("skills_used"):
        lines.append(f"skills_used: {', '.join(entry['skills_used'])}")
    if entry.get("tools_called"):
        lines.append(f"tools_called: {', '.join(entry['tools_called'])}")
    if entry.get("details"):
        lines.append(f"details: {entry['details']}")
    return "\n".join(lines)


def _build_entry(*, root, event, task_id, status, summary, level="INFO",
                 title=None, tokens=None, credits=None, cost=None,
                 skills_used=None, tools_called=None, details="",
                 branch=None) -> dict:
    if branch is None:
        branch = mlib.git_branch(root)
    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3],
        "level": mlib.sanitize(level), "event": event,
        "task_id": mlib.sanitize(task_id), "status": mlib.sanitize(status),
        "summary": mlib.sanitize(summary),
        "title": mlib.sanitize(title) if title else "",
        "branch": mlib.sanitize(branch),
        "last_commit_hash": mlib.sanitize(mlib.git_last_commit(root)),
        "tokens": tokens, "credits": credits, "cost": cost,
        "skills_used": [mlib.sanitize(s) for s in (skills_used or [])],
        "tools_called": [mlib.sanitize(t) for t in (tools_called or [])],
        "details": mlib.sanitize(details),
    }


def _write_entry(root: Path, entry: dict) -> None:
    validate(entry)
    path = _tasks_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    block = render_entry(entry) + "\n" + SEPARATOR + "\n"
    previous = path.read_text(encoding="utf-8") if path.exists() else ""
    path.write_text(block + previous, encoding="utf-8")
    try:
        import render_tasks
        render_tasks.render(root)
    except Exception as err:  # noqa: BLE001 — best-effort view refresh
        print(f"warning: could not refresh Tasks page: {err}", file=sys.stderr)


def start_task(root: Path, *, title, status="open", summary=None, level="INFO",
              tokens=None, credits=None, cost=None, skills_used=None,
              tools_called=None, details="", branch=None) -> str:
    task_id = new_task_id(root)
    entry = _build_entry(root=root, event="task-start", task_id=task_id,
                         status=status, summary=summary or f"started: {title}",
                         level=level, title=title, tokens=tokens, credits=credits,
                         cost=cost, skills_used=skills_used, tools_called=tools_called,
                         details=details, branch=branch)
    _write_entry(root, entry)
    return task_id


def update_task(root: Path, *, task_id, status, summary, level="INFO",
                tokens=None, credits=None, cost=None, skills_used=None,
                tools_called=None, details="", branch=None) -> None:
    if task_id not in _existing_task_ids(root):
        raise ValueError(f"unknown task_id: {task_id!r} (no task-start found for it)")
    entry = _build_entry(root=root, event="task-update", task_id=task_id,
                         status=status, summary=summary, level=level,
                         tokens=tokens, credits=credits, cost=cost,
                         skills_used=skills_used, tools_called=tools_called,
                         details=details, branch=branch)
    _write_entry(root, entry)


def close_task(root: Path, *, task_id, status, summary, level="INFO",
              tokens=None, credits=None, cost=None, skills_used=None,
              tools_called=None, details="", branch=None) -> None:
    if task_id not in _existing_task_ids(root):
        raise ValueError(f"unknown task_id: {task_id!r} (no task-start found for it)")
    entry = _build_entry(root=root, event="task-close", task_id=task_id,
                         status=status, summary=summary, level=level,
                         tokens=tokens, credits=credits, cost=cost,
                         skills_used=skills_used, tools_called=tools_called,
                         details=details, branch=branch)
    _write_entry(root, entry)


def _add_common_args(sp: argparse.ArgumentParser) -> None:
    sp.add_argument("--summary", required=True)
    sp.add_argument("--level", default="INFO", choices=LEVELS)
    sp.add_argument("--tokens", type=float, default=None)
    sp.add_argument("--credits", type=float, default=None)
    sp.add_argument("--cost", type=float, default=None)
    sp.add_argument("--skills-used", nargs="*", default=None)
    sp.add_argument("--tools-called", nargs="*", default=None)
    sp.add_argument("--details", default="")
    sp.add_argument("--branch", default=None)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mlib.add_root_arg(ap)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sp_start = sub.add_parser("start")
    sp_start.add_argument("--title", required=True)
    sp_start.add_argument("--status", default="open", choices=NONTERMINAL)
    sp_start.add_argument("--summary", default=None)
    sp_start.add_argument("--level", default="INFO", choices=LEVELS)
    sp_start.add_argument("--tokens", type=float, default=None)
    sp_start.add_argument("--credits", type=float, default=None)
    sp_start.add_argument("--cost", type=float, default=None)
    sp_start.add_argument("--skills-used", nargs="*", default=None)
    sp_start.add_argument("--tools-called", nargs="*", default=None)
    sp_start.add_argument("--details", default="")
    sp_start.add_argument("--branch", default=None)

    sp_update = sub.add_parser("update")
    sp_update.add_argument("--task-id", required=True)
    sp_update.add_argument("--status", required=True, choices=NONTERMINAL)
    _add_common_args(sp_update)

    sp_close = sub.add_parser("close")
    sp_close.add_argument("--task-id", required=True)
    sp_close.add_argument("--status", required=True, choices=TERMINAL)
    _add_common_args(sp_close)

    args = ap.parse_args()
    root = mlib.resolve_root(args)
    mlib.require_init(root)

    try:
        if args.cmd == "start":
            task_id = start_task(root, title=args.title, status=args.status,
                                 summary=args.summary, level=args.level,
                                 tokens=args.tokens, credits=args.credits,
                                 cost=args.cost, skills_used=args.skills_used,
                                 tools_called=args.tools_called,
                                 details=args.details, branch=args.branch)
            print(f"task started: {task_id} ({args.title})")
        elif args.cmd == "update":
            update_task(root, task_id=args.task_id, status=args.status,
                       summary=args.summary, level=args.level,
                       tokens=args.tokens, credits=args.credits, cost=args.cost,
                       skills_used=args.skills_used, tools_called=args.tools_called,
                       details=args.details, branch=args.branch)
            print(f"task updated: {args.task_id} ({args.status})")
        elif args.cmd == "close":
            close_task(root, task_id=args.task_id, status=args.status,
                      summary=args.summary, level=args.level,
                      tokens=args.tokens, credits=args.credits, cost=args.cost,
                      skills_used=args.skills_used, tools_called=args.tools_called,
                      details=args.details, branch=args.branch)
            print(f"task closed: {args.task_id} ({args.status})")
    except ValueError as err:
        print(f"task command rejected: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
