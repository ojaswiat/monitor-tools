#!/usr/bin/env python3
"""Compute a deterministic project-status snapshot: open tasks, recent logs,
pending state, and a bit of git history. Prints JSON to stdout only -- this
script never writes a file, matching /monitor:status's chat-only-by-default
design. All facts (current activity, next steps) are extracted mechanically
from existing data; no judgment is made in this script.

Usage:
  python3 status.py --project-root <repo> [--log-limit N] [--commit-limit N]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import monitor_lib as mlib
import pending
import render_logs

DEFAULT_LOG_LIMIT = 5
DEFAULT_COMMIT_LIMIT = 5
_FIELD_RE = re.compile(r"^(NEXT|GAPS|ASSUMPTIONS):\s*(.+)$", re.M)


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(root), *args],
                            capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else ""


def git_summary(root: Path, commit_limit: int) -> dict:
    modified = set(l for l in _git(root, "diff", "--name-only").splitlines() if l)
    modified |= set(l for l in _git(root, "diff", "--cached", "--name-only").splitlines() if l)
    untracked = [l for l in _git(root, "ls-files", "--others", "--exclude-standard").splitlines() if l]
    log_out = _git(root, "log", f"-{commit_limit}", "--pretty=format:%h\x1f%s")
    commits = []
    for line in log_out.splitlines():
        if "\x1f" not in line:
            continue
        sha, subject = line.split("\x1f", 1)
        commits.append({"sha": sha, "subject": subject})
    return {
        "uncommitted": {
            "modified": len(modified),
            "untracked": len(untracked),
            "clean": not modified and not untracked,
        },
        "recent_commits": commits,
    }


def _log_entries(root: Path) -> list[dict]:
    path = mlib.monitor_dir(root) / "logs" / "operations.mtr"
    if not path.exists():
        return []
    entries = render_logs.parse_log(path.read_text(encoding="utf-8"))
    return [e for e in entries if "fragment" not in e]


def recent_logs(root: Path, limit: int) -> list[dict]:
    return [
        {"timestamp": e["timestamp"], "operation": e["operation"],
         "status": e["status"], "summary": e["summary"]}
        for e in _log_entries(root)[:limit]
    ]


def current_activity(open_tasks: list[dict], logs: list[dict]) -> dict:
    if open_tasks:
        t = open_tasks[0]
        return {"source": "open_task", "summary": t.get("title") or t.get("task_id", "")}
    if logs:
        return {"source": "last_log", "summary": logs[0]["summary"]}
    return {"source": "none", "summary": ""}


def next_steps(root: Path, log_limit: int) -> list[dict]:
    steps = []
    for e in _log_entries(root)[:log_limit]:
        details = e.get("details", "")
        if not details:
            continue
        text = details.replace("\\n", "\n")
        for m in _FIELD_RE.finditer(text):
            steps.append({"field": m.group(1), "text": m.group(2).strip(),
                          "from_operation": e["operation"]})
    return steps


def compute_status(root: Path, *, log_limit: int = DEFAULT_LOG_LIMIT,
                   commit_limit: int = DEFAULT_COMMIT_LIMIT) -> dict:
    open_tasks = pending.open_tasks(root)
    logs = recent_logs(root, log_limit)
    pending_data = pending.load_pending(root)
    return {
        "branch": mlib.git_branch(root),
        "git": git_summary(root, commit_limit),
        "open_tasks": open_tasks,
        "recent_logs": logs,
        "pending": {
            "logs": pending_data.get("pending_logs", []),
            "report": pending_data.get("pending_report"),
            "task_signal": pending_data.get("pending_task_signal"),
        },
        "current_activity": current_activity(open_tasks, logs),
        "next_steps": next_steps(root, log_limit),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mlib.add_root_arg(ap)
    ap.add_argument("--log-limit", type=int, default=DEFAULT_LOG_LIMIT)
    ap.add_argument("--commit-limit", type=int, default=DEFAULT_COMMIT_LIMIT)
    args = ap.parse_args()
    root = mlib.resolve_root(args)
    mlib.require_init(root)
    status = compute_status(root, log_limit=args.log_limit, commit_limit=args.commit_limit)
    print(json.dumps(status, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
