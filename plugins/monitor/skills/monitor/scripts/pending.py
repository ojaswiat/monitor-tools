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
            "last_report_sha": "", "last_seen_sha": "", "pending_task_signal": None}


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
    except Exception:                                                             
        return False
    return out.returncode == 0


_SEGMENT_RE = re.compile(r"^\s*git\s+(commit|merge|rebase)\b(.*)$")
_EXCLUDED_FLAGS = ("--abort", "--continue", "--dry-run", "--quit")


def _classify(command: str) -> str | None:
    """Return "commit", "merge", or "rebase" if `command` contains a real git
    commit/merge/rebase invocation as one of its shell segments (split on
    &&/||/;/|), skipping --abort/--continue/--dry-run/--quit variants
    (mid-workflow calls that don't represent a completed action). None
    otherwise."""
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
    except Exception:                
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
    except Exception:                
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
    else:                       
                                                                         
                                                                          
                                                                        
                                            
        data["pending_logs"] = [e for e in data["pending_logs"]
                                 if _sha_reachable(root, e["sha"])]
        data["pending_report"] = {
            "event": event, "since_sha": data.get("last_report_sha") or "",
            "detected_at": now,
        }
    if head:
        data["last_seen_sha"] = head
    save_pending(root, data)


INSTRUCTIONS = (
    "If Y: read monitor/.pending.json. For each pending_logs entry, run "
    "/monitor:log for it (its stored message is a starting point — "
    "DECISION/WHY/etc are still your judgment). When more than one entry is "
    "pending, pass --last-commit-hash <that entry's sha> to /monitor:log for "
    "every entry that is not the current HEAD, so each log clears its own "
    "entry instead of always clearing HEAD's. For a set pending_report, "
    "run `git log <since_sha>..HEAD` (since_sha is in monitor/.pending.json; "
    "if it's empty, this is the first report ever — use the full branch "
    "history instead, e.g. `git log HEAD` or against the branch's actual "
    "base) to get the real commit range, then author one /monitor:report "
    "covering it. Continue with the user's original request afterward.\n"
    "If N: say \"Skipping monitor. What next?\" and leave "
    "monitor/.pending.json untouched — it stays pending and will remind "
    "again next turn."
)

                                                                            
                                                           
WARNING = ("[Warn!] Monitor: Pending logs and report. Do you want Monitor to "
           "record now [Y/N]\n\n" + INSTRUCTIONS)


_PLAN_PATH_RE = re.compile(r"(?:^|/)(plans|specs)/[^/]+\.md$", re.I)


def _looks_like_plan_file(path: str) -> bool:
    """True for a Write to any *.md file under a "plans" or "specs" directory
    at any depth (docs/superpowers/plans/x.md, docs/plans/x.md, specs/x.md,
    ...) — generic, not tied to any one companion skill's own convention, so
    the signal fires the same whether or not superpowers is installed."""
    return bool(_PLAN_PATH_RE.search(path.replace("\\", "/")))


def track_task_signal(root: Path, path: str) -> None:
    """Record that a plan/spec file was written with no task currently
    tracking the work. No-op if a task is already open — an agent mid-task
    writing more plan files shouldn't get re-nagged."""
    if open_tasks(root):
        return
    data = load_pending(root)
    data["pending_task_signal"] = {
        "path": path, "detected_at": datetime.now().isoformat(timespec="seconds"),
    }
    save_pending(root, data)


def clear_task_signal(root: Path) -> None:
    data = load_pending(root)
    data["pending_task_signal"] = None
    save_pending(root, data)


def open_tasks(root: Path) -> list[dict]:
    """Every task whose most-recent status is non-terminal, i.e. still open."""
    try:
        import render_tasks
    except Exception:                                                     
        return []                                                        
    path = mlib.monitor_dir(root) / "tasks" / "tasks.mtr"
    if not path.exists():
        return []
    entries = render_tasks.parse_tasks(path.read_text(encoding="utf-8"))
    groups = render_tasks.group_tasks(entries)
    return [{"task_id": g["task_id"], "title": g["title"], "status": g["status"]}
            for g in groups if g["status"] in render_tasks.NONTERMINAL]


def _join(parts: list[str]) -> str:
    """"a", "a and b", "a, b, and c" — plain English joining (Oxford comma)."""
    if len(parts) <= 2:
        return " and ".join(parts)
    return ", ".join(parts[:-1]) + ", and " + parts[-1]


def _pending_phrase(data: dict, n_open_tasks: int) -> str:
    """"logs", "report", "N open task(s)", or a joined combination — only
    what is really pending. Used to decide *whether* anything is pending;
    check_text() builds the Y/N header from the log/report parts alone,
    since answering Y never closes a task."""
    parts = []
    if data.get("pending_logs"):
        parts.append("logs")
    if data.get("pending_report"):
        parts.append("report")
    if n_open_tasks:
        parts.append(f"{n_open_tasks} open task{'s' if n_open_tasks != 1 else ''}")
    return _join(parts)


TASKS_ONLY_INSTRUCTIONS = (
    "These tasks are informational — close them with /monitor:task-close when "
    "done, or keep working; this does not block you."
)


def _task_block(tasks: list[dict]) -> str:
    task_lines = "\n".join(
        f"  - {t['task_id']}  ({t['status']})  {t['title']}" for t in tasks)
    return ("\nOpen tasks (close with /monitor:task-close when done, "
            "or leave open and continue — this is informational, "
            "not blocking):\n" + task_lines)


def _task_signal_line(signal: dict) -> str:
    return (f"A plan/spec file was written ({signal['path']}) with no task "
            f"tracking this work. Start one with /monitor:task-start if this "
            f"is a multi-step unit — informational, not blocking.")


def check_text(root: Path) -> str:
    data = load_pending(root)
    tasks = open_tasks(root)
                                                                           
                                                                           
                                                                      
    task_signal = data.get("pending_task_signal") if not tasks else None
    phrase = _pending_phrase(data, len(tasks))
    if not phrase and not task_signal:
        return ""
    needs_record = bool(data.get("pending_logs") or data.get("pending_report"))
    if not needs_record:
        if tasks:
                                                                       
                                                                         
                                                                         
                                                                 
            noun = "task" if len(tasks) == 1 else "tasks"
            return "\n".join([f"[Warn!] Monitor: {len(tasks)} open {noun}.", "",
                              TASKS_ONLY_INSTRUCTIONS, _task_block(tasks)])
                                                                
        return "\n".join(["[Warn!] Monitor: no task tracked for recent "
                          "plan/spec work.", "", _task_signal_line(task_signal)])
                                                                            
                                                                            
                                 
    record_phrase = _pending_phrase(data, 0)
    header = (f"[Warn!] Monitor: Pending {record_phrase}. Do you want Monitor to "
              f"record now [Y/N]")
    lines = [header, "", INSTRUCTIONS]
    if tasks:
        noun = "task" if len(tasks) == 1 else "tasks"
        lines.append(f"\nSeparately, {len(tasks)} open {noun} — not part of "
                     f"the Y/N above.")
        lines.append(_task_block(tasks))
    if task_signal:
        lines.append("\n" + _task_signal_line(task_signal))
    return "\n".join(lines)


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
    """PostToolUse hook entrypoint. Silent no-op unless the tool call that
    just ran was either a git commit/merge/rebase (Bash) or a Write to a
    plan/spec markdown file with no task open — matcher covers both tool
    names, so this reads tool_input itself to tell them apart."""
    if not _monitor_initialized(root):
        return
    try:
        payload = json.load(sys.stdin)
    except Exception:                                                       
        return
    tool_name = payload.get("tool_name") or ""
    tool_input = payload.get("tool_input") or {}
    if tool_name == "Bash":
        event = _classify(tool_input.get("command", "") or "")
        if event:
            track(root, event, None, "")
    elif tool_name == "Write":
        path = tool_input.get("file_path", "") or ""
        if path and _looks_like_plan_file(path):
            track_task_signal(root, path)


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
