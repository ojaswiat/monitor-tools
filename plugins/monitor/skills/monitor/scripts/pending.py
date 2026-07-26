#!/usr/bin/env python3
"""Track and check monitor's pending log/report state (monitor/.pending.json).

Stdlib-only. `track` and `check` are the plain, directly-testable CLI
commands; `hook-post-tool-use` and `hook-user-prompt-submit` are the actual
Claude Code hook entrypoints that speak the real hook I/O contract (JSON on
stdin; UserPromptSubmit prints a hookSpecificOutput envelope to inject
context). See "Pending-state enforcement" in SKILL.md.

Usage:
  python3 pending.py --project-root <repo> track --event commit --sha <sha> --message "<msg>"
  python3 pending.py --project-root <repo> track --event merge
  python3 pending.py --project-root <repo> check
  echo '{"tool_name": "Bash", "tool_input": {"command": "git commit -m x"}}' | python3 pending.py --project-root <repo> hook-post-tool-use
  echo '{}' | python3 pending.py --project-root <repo> hook-user-prompt-submit
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import monitor_lib as mlib

_DEFAULT = {"branch": "", "pending_logs": [], "pending_report": None,
            "last_report_sha": "", "last_seen_sha": ""}


def pending_path(root: Path) -> Path:
    return mlib.monitor_dir(root) / ".pending.json"


def load_pending(root: Path) -> dict:
    data = mlib.load_json(pending_path(root), copy.deepcopy(_DEFAULT))
    for key, default in _DEFAULT.items():
        if key not in data:
            data[key] = copy.deepcopy(default)
    return data


def save_pending(root: Path, data: dict) -> None:
    mlib.save_json(pending_path(root), data)


def _sha_reachable(root: Path, sha: str) -> bool:
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "merge-base", "--is-ancestor", sha, "HEAD"],
            capture_output=True, timeout=5)
    except Exception:  # noqa: BLE001 — git missing/unusable means "not reachable"
        return False
    return out.returncode == 0


_SEGMENT_RE = re.compile(r"^\s*git\s+(commit|merge|rebase)\b(.*)$")
_EXCLUDED_FLAGS = ("--abort", "--dry-run", "--quit")


def _classify(command: str) -> str | None:
    """Return "commit", "merge", or "rebase" if `command` contains a real git
    commit/merge/rebase invocation as one of its shell segments (split on
    &&/||/;/|), skipping --abort/--dry-run/--quit variants (mid-workflow
    calls that don't represent a completed action). None otherwise."""
    for segment in re.split(r"&&|\|\||;|\|", command):
        m = _SEGMENT_RE.match(segment)
        if not m:
            continue
        verb, rest = m.group(1), m.group(2)
        if any(flag in rest for flag in _EXCLUDED_FLAGS):
            continue
        return verb
    return None


def _commit_subject(root: Path, sha: str) -> str:
    try:
        out = subprocess.run(["git", "-C", str(root), "log", "-1", "--pretty=%s", sha],
                              capture_output=True, text=True, timeout=5)
    except Exception:  # noqa: BLE001
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def _commit_touches_only_monitor(root: Path, sha: str) -> bool:
    """True if every file this commit changed is under monitor/ — a commit
    that's only the monitor log/report itself shouldn't re-trigger the
    pending gate (otherwise every /monitor:log commit warns about itself)."""
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "show", "--name-only", "--pretty=format:", sha],
            capture_output=True, text=True, timeout=5)
    except Exception:  # noqa: BLE001
        return False
    files = [f for f in out.stdout.splitlines() if f.strip()]
    return bool(files) and all(f.startswith("monitor/") for f in files)


def track(root: Path, event: str, sha: str | None, message: str) -> None:
    data = load_pending(root)
    data["branch"] = mlib.git_branch(root)
    head = sha or mlib.git_last_commit(root)
    now = datetime.now().isoformat(timespec="seconds")
    if event == "commit":
        if (head and head != data.get("last_seen_sha")
                and not _commit_touches_only_monitor(root, head)
                and not any(e["sha"] == head for e in data["pending_logs"])):
            data["pending_logs"].append({
                "sha": head, "message": _commit_subject(root, head) or message,
                "committed_at": now,
            })
    else:  # "merge" or "rebase"
        # Rebase rewrites shas — drop any pending_logs entry whose sha no
        # longer resolves; its content is folded into the report range via
        # since_sha instead of tracked individually. A no-op filter on a
        # plain merge (no rewrite happened).
        data["pending_logs"] = [e for e in data["pending_logs"]
                                 if _sha_reachable(root, e["sha"])]
        data["pending_report"] = {
            "event": event, "since_sha": data.get("last_report_sha") or "",
            "detected_at": now,
        }
    if head:
        data["last_seen_sha"] = head
    save_pending(root, data)


WARNING = (
    "[Warn!] Monitor: Pending logs and report. Do you want Monitor to record now [Y/N]\n\n"
    "If Y: read monitor/.pending.json. For each pending_logs entry, run "
    "/monitor:log for it (its stored message is a starting point — "
    "DECISION/WHY/etc are still your judgment). For a set pending_report, "
    "run `git log <since_sha>..HEAD` (since_sha is in monitor/.pending.json; "
    "if it's empty, this is the first report ever — use the full branch "
    "history instead, e.g. `git log HEAD` or against the branch's actual "
    "base) to get the real commit range, then author one /monitor:report "
    "covering it. Continue with the user's original request afterward.\n"
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
    """Clear one pending commit per logged operation.

    Prefers the entry whose sha matches exactly. When several commits landed
    before any of them was logged, every catch-up log is written at the same
    HEAD, so no exact match exists for the older ones — fall back to draining
    the oldest already-reached entry. Without that fallback those entries can
    never be cleared and the warning sticks forever."""
    data = load_pending(root)
    entries = data["pending_logs"]
    for i, entry in enumerate(entries):
        if entry["sha"] == sha:
            del entries[i]
            break
    else:
        for i, entry in enumerate(entries):
            if _sha_reachable(root, entry["sha"]):
                del entries[i]
                break
    data["pending_logs"] = entries
    save_pending(root, data)


def clear_report(root: Path) -> None:
    data = load_pending(root)
    data["pending_report"] = None
    data["last_report_sha"] = mlib.git_last_commit(root)
    save_pending(root, data)


def _monitor_initialized(root: Path) -> bool:
    return (mlib.monitor_dir(root) / "profile.json").exists()


def hook_post_tool_use(root: Path) -> None:
    """PostToolUse hook entrypoint. Silent no-op unless the Bash command that
    just ran was a git commit/merge/rebase — matcher only filters on tool
    name ("Bash"), so this reads tool_input.command itself to self-filter."""
    if not _monitor_initialized(root):
        return
    try:
        payload = json.load(sys.stdin)
    except Exception:  # noqa: BLE001 — malformed/empty stdin, nothing to do
        return
    if (payload.get("tool_name") or "") != "Bash":
        return
    command = (payload.get("tool_input") or {}).get("command", "") or ""
    event = _classify(command)
    if event:
        track(root, event, None, "")


def hook_user_prompt_submit(root: Path) -> None:
    """UserPromptSubmit hook entrypoint. Prints the JSON envelope Claude Code
    requires to inject additionalContext; prints nothing if not initialized
    or nothing is pending."""
    if not _monitor_initialized(root):
        return
    text = check_text(root)
    if text:
        print(json.dumps({
            "continue": True,
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": text,
            },
        }))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mlib.add_root_arg(ap)
    sub = ap.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("track")
    t.add_argument("--event", required=True, choices=("commit", "merge", "rebase"))
    t.add_argument("--sha", default=None)
    t.add_argument("--message", default="")

    sub.add_parser("check")
    sub.add_parser("hook-post-tool-use")
    sub.add_parser("hook-user-prompt-submit")

    args = ap.parse_args()
    root = mlib.resolve_root(args)

    if args.cmd == "hook-post-tool-use":
        hook_post_tool_use(root)
        return 0
    if args.cmd == "hook-user-prompt-submit":
        hook_user_prompt_submit(root)
        return 0

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
