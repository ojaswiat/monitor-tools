#!/usr/bin/env python3
"""Track and check monitor's pending log/report state (monitor/.pending.json).

Stdlib-only. `track` and `check` are the plain, directly-testable CLI
commands; `hook-post-tool-use` and `hook-user-prompt-submit` (added in a
later task) are the actual Claude Code hook entrypoints that speak the real
hook I/O contract. See "Pending-state enforcement" in SKILL.md.

Usage:
  python3 pending.py --project-root <repo> track --event commit --sha <sha> --message "<msg>"
  python3 pending.py --project-root <repo> track --event merge
  python3 pending.py --project-root <repo> check
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import monitor_lib as mlib

_DEFAULT = {"branch": "", "pending_logs": [], "pending_report": None,
            "last_report_sha": ""}


def pending_path(root: Path) -> Path:
    return mlib.monitor_dir(root) / ".pending.json"


def load_pending(root: Path) -> dict:
    data = mlib.load_json(pending_path(root), dict(_DEFAULT))
    for key, default in _DEFAULT.items():
        data.setdefault(key, default)
    return data


def save_pending(root: Path, data: dict) -> None:
    mlib.save_json(pending_path(root), data)


def _sha_exists(root: Path, sha: str) -> bool:
    try:
        out = subprocess.run(["git", "-C", str(root), "cat-file", "-e", sha],
                              capture_output=True, timeout=5)
    except Exception:  # noqa: BLE001 — git missing/unusable means "doesn't exist"
        return False
    return out.returncode == 0


def track(root: Path, event: str, sha: str | None, message: str) -> None:
    data = load_pending(root)
    data["branch"] = mlib.git_branch(root)
    head = sha or mlib.git_last_commit(root)
    now = datetime.now().isoformat(timespec="seconds")
    if event == "commit":
        if head and not any(e["sha"] == head for e in data["pending_logs"]):
            data["pending_logs"].append(
                {"sha": head, "message": message, "committed_at": now})
    else:  # "merge" or "rebase"
        # Rebase rewrites shas — drop any pending_logs entry whose sha no
        # longer resolves; its content is folded into the report range via
        # since_sha instead of tracked individually. A no-op filter on a
        # plain merge (no rewrite happened).
        data["pending_logs"] = [e for e in data["pending_logs"]
                                 if _sha_exists(root, e["sha"])]
        data["pending_report"] = {
            "event": event, "since_sha": data.get("last_report_sha") or "",
            "detected_at": now,
        }
    save_pending(root, data)


WARNING = (
    "[Warn!] Monitor: Pending logs and report. Do you want Monitor to record now [Y/N]\n\n"
    "If Y: read monitor/.pending.json. For each pending_logs entry, run "
    "/monitor:log for it (its stored message is a starting point — "
    "DECISION/WHY/etc are still your judgment). For a set pending_report, "
    "run `git log <since_sha>..HEAD` (since_sha is in monitor/.pending.json) "
    "to get the real commit range, then author one /monitor:report covering "
    "it. Continue with the user's original request afterward.\n"
    "If N: say \"Skipping monitor. What next?\" and leave "
    "monitor/.pending.json untouched — it stays pending and will remind "
    "again next turn."
)


def check_text(root: Path) -> str:
    data = load_pending(root)
    if data.get("pending_logs") or data.get("pending_report"):
        return WARNING
    return ""


def clear_log(root: Path, sha: str) -> None:
    data = load_pending(root)
    data["pending_logs"] = [e for e in data["pending_logs"] if e["sha"] != sha]
    save_pending(root, data)


def clear_report(root: Path) -> None:
    data = load_pending(root)
    data["pending_report"] = None
    data["last_report_sha"] = mlib.git_last_commit(root)
    save_pending(root, data)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mlib.add_root_arg(ap)
    sub = ap.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("track")
    t.add_argument("--event", required=True, choices=("commit", "merge", "rebase"))
    t.add_argument("--sha", default=None)
    t.add_argument("--message", default="")

    sub.add_parser("check")

    args = ap.parse_args()
    root = mlib.resolve_root(args)
    mlib.require_init(root)

    if args.cmd == "track":
        track(root, args.event, args.sha, args.message)
    elif args.cmd == "check":
        text = check_text(root)
        if text:
            print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
