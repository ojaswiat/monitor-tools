#!/usr/bin/env python3
"""Delete the oldest N logs, reports, or tasks, then re-render the affected pages.

Usage:
  python3 clean.py --project-root <repo> --logs N
  python3 clean.py --project-root <repo> --reports N
  python3 clean.py --project-root <repo> --tasks N
  add --dry-run to preview without deleting.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import monitor_lib as mlib
import render_logs
import render_report
import render_tasks

SEPARATOR = "=" * 80


def clean_logs(root: Path, n: int, dry: bool) -> int:
    log_path = mlib.monitor_dir(root) / "logs" / "operations.mtr"
    if not log_path.exists():
        print("no operations.mtr")
        return 0
    text = log_path.read_text(encoding="utf-8")
    blocks = [b for b in text.split(SEPARATOR + "\n") if b.strip("\n")]                
    n = max(0, min(n, len(blocks)))
    kept = blocks[:len(blocks) - n]
    print(f"removing {n} oldest of {len(blocks)} log entries")
    if dry:
        return 0
    new_text = "".join(b + SEPARATOR + "\n" for b in kept)
    log_path.write_text(new_text, encoding="utf-8")
    render_logs.render(root)
    render_report.refresh_dashboard(root)
    return 0


def clean_reports(root: Path, n: int, dry: bool) -> int:
    mdir = mlib.monitor_dir(root)
    items = render_report.scan_reports(root)                        
    n = max(0, min(n, len(items)))
    kept = items[:len(items) - n]
    removed = items[len(items) - n:]
    print(f"removing {n} oldest of {len(items)} reports:")
    for it in removed:
        print(f"  - {it['file']}  ({it['title']})")
    if dry:
        return 0
    for it in removed:
        f = mdir / "reports" / it["file"]
        if f.exists():
            f.unlink()
    profile = mlib.load_profile(root)
    branch = mlib.git_branch(root)
    render_report.render_reports_index(profile, kept, root, branch)
    render_report.render_dashboard(profile, len(kept), root, branch)
    return 0


def clean_tasks(root: Path, n: int, dry: bool) -> int:
    tasks_path = mlib.monitor_dir(root) / "tasks" / "tasks.mtr"
    if not tasks_path.exists():
        print("no tasks.mtr")
        return 0
    text = tasks_path.read_text(encoding="utf-8")
    entries = render_tasks.parse_tasks(text)
    groups = render_tasks.group_tasks(entries)
                                                                             
                                                                             
                                                                            
                                                                            
                                                                         
    order = sorted(range(len(groups)),
                   key=lambda i: (groups[i]["created_at"], -i))
    groups = [groups[i] for i in order]
    n = max(0, min(n, len(groups)))
    removed = groups[:n]
    to_remove = {g["task_id"] for g in removed}
    print(f"removing {n} oldest of {len(groups)} tasks (all their events):")
    for g in removed:
        print(f"  - {g['task_id']}  ({g['title'] or 'untitled'})")
    if dry:
        return 0
                                                                          
                                                                         
                                                                            
                         
    kept_blocks = [b for b in render_tasks.split_blocks(text)
                   if render_tasks.block_task_id(b) not in to_remove]
    new_text = "".join(b + "\n" + SEPARATOR + "\n" for b in kept_blocks)
    tasks_path.write_text(new_text, encoding="utf-8")
    render_tasks.render(root)
    render_report.refresh_dashboard(root)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mlib.add_root_arg(ap)
    ap.add_argument("--logs", type=int, help="Delete the oldest N log entries")
    ap.add_argument("--reports", type=int, help="Delete the oldest N reports")
    ap.add_argument("--tasks", type=int, help="Delete the oldest N tasks (all their events)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    root = mlib.resolve_root(args)
    mlib.require_init(root)
    if args.logs is not None:
        return clean_logs(root, args.logs, args.dry_run)
    if args.reports is not None:
        return clean_reports(root, args.reports, args.dry_run)
    if args.tasks is not None:
        return clean_tasks(root, args.tasks, args.dry_run)
    ap.error("one of --logs, --reports, or --tasks is required")


if __name__ == "__main__":
    sys.exit(main())
