#!/usr/bin/env python3
"""Search monitor's logs, reports, and tasks for matches to a query.

Stdlib-only, plain-text output (no HTML page) — built for an agent to call
and read directly, like grep over the monitor folder. `--scope` picks the
source: `logs` searches operations.mtr, `reports` searches the visible text
of reports/*.html, `tasks` searches tasks.mtr, and `all` (the default)
searches every source and groups the output by source. `--branch`,
`--status`, and `--level` filter log matches only. Reuses
render_logs.parse_log() / render_tasks.parse_tasks() / the report scan so
matching stays in sync with how entries are actually parsed.

Usage:
  python3 search.py --project-root <repo> --query "auth bug" \\
      [--scope logs|reports|tasks|all] \\
      [--branch <name>] [--status success|partial|failure] [--level LEVEL] \\
      [--limit N]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import logger
import monitor_lib as mlib
import render_logs
import render_report
import render_tasks


def _haystack(e: dict) -> str:
    parts = [e.get("operation", ""), e.get("tool", ""), e.get("summary", ""),
              e.get("task_id", ""), e.get("details", ""), e.get("branch", ""),
              e.get("last_commit_hash", "")]
    parts += [f"{k} {v}" for k, v in e.get("extra", {}).items()]
    return " ".join(parts).lower()


def search(root: Path, query: str, *, scope: str = "logs", branch: str | None = None,
           status: str | None = None, level: str | None = None,
           limit: int = 20):
    """scope="logs" (default) returns list[dict] — the original, unchanged
    behavior every existing caller relies on. scope="reports"/"tasks" return
    list[dict] from search_reports()/search_tasks(). scope="all" returns a
    dict {"logs": [...], "reports": [...], "tasks": [...]}."""
    if scope == "reports":
        return search_reports(root, query, limit=limit)
    if scope == "tasks":
        return search_tasks(root, query, limit=limit)
    if scope == "all":
        return {
            "logs": _search_logs(root, query, branch=branch, status=status,
                                 level=level, limit=limit),
            "reports": search_reports(root, query, limit=limit),
            "tasks": search_tasks(root, query, limit=limit),
        }
    return _search_logs(root, query, branch=branch, status=status, level=level, limit=limit)


def _search_logs(root: Path, query: str, *, branch: str | None = None,
                 status: str | None = None, level: str | None = None,
                 limit: int = 20) -> list[dict]:
    if limit <= 0:
        return []
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


def search_reports(root: Path, query: str, *, limit: int = 20) -> list[dict]:
    if limit <= 0:
        return []
    q = query.lower()
    matches = []
                                                                        
                                                         
    for item in render_report.scan_reports(root, with_text=True):
        raw = item.pop("text")
                                                                      
                                                                    
                                                               
        raw = render_report.STYLE_RE.sub("", raw)
        raw = render_report.SCRIPT_RE.sub("", raw)
        text = render_report._plain(raw)
        if q not in text.lower():
            continue
        idx = text.lower().find(q)
        start = max(0, idx - 40)
        excerpt = text[start:idx + len(query) + 40].strip()
        matches.append({"file": item["file"], "title": item["title"],
                        "date": item["date"], "excerpt": excerpt})
        if len(matches) >= limit:
            break
    return matches


def search_tasks(root: Path, query: str, *, limit: int = 20) -> list[dict]:
    if limit <= 0:
        return []
    tasks_path = mlib.monitor_dir(root) / "tasks" / "tasks.mtr"
    if not tasks_path.exists():
        return []
    entries = render_tasks.parse_tasks(tasks_path.read_text(encoding="utf-8"))
    q = query.lower()
    matches = []
    for e in entries:
        haystack = " ".join([e.get("title", ""), e.get("summary", ""),
                             e.get("details", "")]).lower()
        if q not in haystack:
            continue
        matches.append(e)
        if len(matches) >= limit:
            break
    return matches


def format_report_match(m: dict) -> str:
    return f"{m['date']}  {m['title']}  ({m['file']})\n  ...{m['excerpt']}..."


def format_task_match(e: dict) -> str:
    lines = [f"{e['timestamp']} {e['level']} [{e['event']}] "
             f"({e['task_id']}) {e['summary']} -- {e['status']}"]
    if e.get("title"):
        lines.append(f"  title:   {e['title']}")
    if e.get("details"):
        lines.append(f"  details: {e['details']}")
    return "\n".join(lines)


def format_match(e: dict) -> str:
    lines = [f"{e['timestamp']} {e['level']} [{e['operation']}] "
              f"({e['tool']}) {e['summary']} -- {e['status']}"]
    if e.get("branch"):
        lines.append(f"  branch:  {e['branch']}")
    if e.get("last_commit_hash"):
        lines.append(f"  commit:  {e['last_commit_hash']}")
    if e.get("task_id"):
        lines.append(f"  task_id: {e['task_id']}")
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
                    help="Case-insensitive substring. In logs it is matched across "
                         "operation, tool, summary, task_id, details, branch, commit, "
                         "and extra fields; in reports across the rendered text of each "
                         "report; in tasks across title, summary, and details.")
    ap.add_argument("--scope", default="all", choices=("logs", "reports", "tasks", "all"),
                    help="Which source to search: logs, reports, tasks, or all "
                         "(default: all, grouped by source in the output).")
    ap.add_argument("--branch", default=None, help="Filter log matches by branch.")
    ap.add_argument("--status", default=None, choices=logger.STATUSES,
                    help="Filter log matches by status.")
    ap.add_argument("--level", default=None, choices=logger.LEVELS,
                    help="Filter log matches by level.")
    ap.add_argument("--limit", type=int, default=20,
                    help="Maximum matches to return. Under --scope all it applies "
                         "per source (logs, reports, tasks) rather than to the "
                         "combined total, so up to 3x this many matches can print.")
    args = ap.parse_args()
    root = mlib.resolve_root(args)
    mlib.require_init(root)
    if args.scope in ("reports", "tasks") and (args.branch or args.status or args.level):
        print("warning: --branch/--status/--level only filter log matches; "
              f"they have no effect under --scope {args.scope}", file=sys.stderr)
    matches = search(root, args.query, scope=args.scope, branch=args.branch,
                     status=args.status, level=args.level, limit=args.limit)
    if args.scope != "all":
        formatter = {"logs": format_match, "reports": format_report_match,
                    "tasks": format_task_match}[args.scope]
        if not matches:
            print(f"no matches for {args.query!r}")
            return 0
        print(f"{len(matches)} match(es) for {args.query!r}:\n")
        for m in matches:
            print(formatter(m))
            print("-" * 80)
        return 0
    total = sum(len(v) for v in matches.values())
    if total == 0:
        print(f"no matches for {args.query!r}")
        return 0
    print(f"{total} match(es) for {args.query!r}:\n")
    for source, formatter in (("logs", format_match), ("reports", format_report_match),
                              ("tasks", format_task_match)):
        if not matches[source]:
            continue
        print(f"## {source}\n")
        for m in matches[source]:
            print(formatter(m))
            print("-" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(main())
