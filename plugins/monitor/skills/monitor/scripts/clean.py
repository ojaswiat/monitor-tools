#!/usr/bin/env python3
"""Delete the most recent N logs or reports, then re-render the affected pages.

Usage:
  python3 clean.py --project-root <repo> --logs N
  python3 clean.py --project-root <repo> --reports N
  add --dry-run to preview without deleting.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import monitor_lib as mlib
import render_logs
import render_report

SEPARATOR = "=" * 80


def clean_logs(root: Path, n: int, dry: bool) -> int:
    log_path = mlib.monitor_dir(root) / "logs" / "operations.mtr"
    if not log_path.exists():
        print("no operations.mtr")
        return 0
    text = log_path.read_text(encoding="utf-8")
    blocks = [b for b in text.split(SEPARATOR + "\n") if b.strip("\n")]
    n = max(0, min(n, len(blocks)))
    kept = blocks[n:]
    print(f"removing {n} newest of {len(blocks)} log entries")
    if dry:
        return 0
    new_text = "".join(b + SEPARATOR + "\n" for b in kept)
    log_path.write_text(new_text, encoding="utf-8")
    render_logs.render(root)
    return 0


def clean_reports(root: Path, n: int, dry: bool) -> int:
    mdir = mlib.monitor_dir(root)
    items = render_report.scan_reports(root)  # already newest-first
    n = max(0, min(n, len(items)))
    removed = items[:n]
    kept = items[n:]
    print(f"removing {n} newest of {len(items)} reports:")
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mlib.add_root_arg(ap)
    ap.add_argument("--logs", type=int, help="Delete the newest N log entries")
    ap.add_argument("--reports", type=int, help="Delete the newest N reports")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    root = mlib.resolve_root(args)
    mlib.require_init(root)
    if args.logs is not None:
        return clean_logs(root, args.logs, args.dry_run)
    if args.reports is not None:
        return clean_reports(root, args.reports, args.dry_run)
    ap.error("one of --logs or --reports is required")


if __name__ == "__main__":
    sys.exit(main())
