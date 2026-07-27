# Tasks Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a third first-class monitor entity — lifecycle-tracked tasks with self-reported metrics — mirroring the existing log system's append-only-text-file + render-script pattern.

**Architecture:** `monitor/tasks/tasks.mtr` is an append-only text log (same block format as `operations.mtr`) written by a new `tasks.py` engine script (`start`/`update`/`close` subcommands). A new `render_tasks.py` groups blocks by `task_id` into cards and renders paginated `monitor/tasks/index.html`, linked from a third Dashboard tab. `logger.py` drops its free-text `--task` field in favor of an optional `--task-id` foreign key.

**Tech Stack:** Python 3 stdlib only (no new dependencies). No test framework exists in this repo (per `CLAUDE.md` — "no build step, package manager, or test suite"); every verification step below is a manual `python3 <script>.py ...` invocation against a scratch temp directory, inspected with `grep`/`cat`, matching this repo's own "Testing changes locally" convention.

## Global Constraints

- Engine stays stdlib-only Python 3 — no new imports beyond `argparse`, `re`, `sys`, `uuid`, `pathlib.Path`, `datetime`.
- Every script resolves its own project root via `mlib.resolve_root(args)` and calls `mlib.require_init(root)` before doing anything else (locked convention, `CLAUDE.md` "Init-gated").
- `tasks.mtr` uses the exact same physical format as `operations.mtr`: `"=" * 80`-separated blocks, newest-first, one header line + `key: value` lines.
- Status enum is fixed: `open, in_progress, needs_approval, needs_retry, blocked, success, failed, cancelled` — first 5 non-terminal, last 3 terminal. `task-start`/`task-update` require a non-terminal status; `task-close` requires a terminal one.
- No changes to `mlib.PALETTE_CSS` — reuse existing `.logcard`/`.tag`/`.kpi`/`.toolchip`/`.pagenav` classes verbatim for the Tasks page.
- All work happens on branch `feat/monitor-tasks` (already checked out).

---

### Task 1: Extract shared `sanitize()` into `monitor_lib.py`

**Files:**
- Modify: `plugins/monitor/skills/monitor/scripts/monitor_lib.py` (add function)
- Modify: `plugins/monitor/skills/monitor/scripts/logger.py:31-47` (use the shared version)

**Interfaces:**
- Produces: `mlib.sanitize(value: str | None) -> str | None` — strips ASCII control chars, flattens real newlines to spaces, trims. Used by `logger.py` today and by `tasks.py` in Task 2.

- [ ] **Step 1: Add `sanitize()` to `monitor_lib.py`**

Insert after `now_stamp()` (after line 111, before the `# ---- vcs` section):

```python
# Strips ASCII control bytes (NUL..BS, VT, FF, SO..US, DEL) — e.g. the raw
# ANSI escape codes a backtick-quoted example command can splice into a field
# via accidental shell command substitution. Tab is left alone; real newlines
# are handled separately since they'd break the block format.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize(value):
    """Every field written to an .mtr file is sanitized first: strip control
    characters, flatten real newlines to spaces (the log is block/line-based —
    a raw newline inside a field would corrupt parsing), and trim."""
    if value is None:
        return value
    value = str(value).replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    return _CONTROL_CHARS.sub("", value).strip()
```

- [ ] **Step 2: Remove the duplicate from `logger.py`, import the shared one**

In `logger.py`, delete lines 31-47 (the `_CONTROL_CHARS` regex and `sanitize()` function). Replace every `sanitize(` call in the file with `mlib.sanitize(`. There are calls in `log_operation()` (lines 91-97) and none elsewhere.

- [ ] **Step 3: Verify logger.py still works**

Run:
```bash
cd /Users/ojaswi/Projects/monitor-tools
mkdir -p /tmp/monitor-task-test && cd /tmp/monitor-task-test
python3 /Users/ojaswi/Projects/monitor-tools/plugins/monitor/skills/monitor/scripts/profile.py --project-root .
mkdir -p monitor/scripts && cp /Users/ojaswi/Projects/monitor-tools/plugins/monitor/skills/monitor/scripts/*.py monitor/scripts/
python3 monitor/scripts/logger.py --project-root . --operation test-op --tool Bash --summary "sanity check" --status success
grep -q "sanity check" monitor/logs/operations.mtr && echo "PASS: logger.py still writes entries"
```
Expected: `PASS: logger.py still writes entries` printed, no traceback.

- [ ] **Step 4: Commit**

```bash
cd /Users/ojaswi/Projects/monitor-tools
git add plugins/monitor/skills/monitor/scripts/monitor_lib.py plugins/monitor/skills/monitor/scripts/logger.py
git commit -m "refactor: extract sanitize() into monitor_lib.py, shared by logger.py and the upcoming tasks.py"
```

---

### Task 2: `tasks.py` — engine script (start / update / close)

**Files:**
- Create: `plugins/monitor/skills/monitor/scripts/tasks.py`

**Interfaces:**
- Consumes: `mlib.sanitize()` (Task 1), `mlib.monitor_dir()`, `mlib.git_branch()`, `mlib.git_last_commit()`, `mlib.resolve_root()`, `mlib.add_root_arg()`, `mlib.require_init()`.
- Produces: `tasks.STATUSES`, `tasks.NONTERMINAL`, `tasks.TERMINAL` tuples; `tasks.start_task(root, *, title, status="open", summary=None, level="INFO", tokens=None, credits=None, cost=None, skills_used=None, tools_called=None, details="", branch=None) -> str` (returns `task_id`); `tasks.update_task(root, *, task_id, status, summary, ...)`; `tasks.close_task(root, *, task_id, status, summary, ...)`. All raise `ValueError` on invalid input. Consumed by `render_tasks.py` (Task 3, reads `tasks.mtr` directly, no function-level dependency) and by the three new command files (Task 6, via CLI).

- [ ] **Step 1: Write `tasks.py`**

```python
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
```

- [ ] **Step 2: Verify start/update/close write valid blocks (render_tasks.py doesn't exist yet — expect the warning, that's fine)**

```bash
cd /tmp/monitor-task-test
cp /Users/ojaswi/Projects/monitor-tools/plugins/monitor/skills/monitor/skills/monitor/scripts/tasks.py monitor/scripts/ 2>/dev/null || \
  cp /Users/ojaswi/Projects/monitor-tools/plugins/monitor/skills/monitor/scripts/tasks.py monitor/scripts/
TID=$(python3 monitor/scripts/tasks.py --project-root . start --title "Ship the tasks feature" | grep -oE '[a-f0-9]{8}')
echo "got task id: $TID"
python3 monitor/scripts/tasks.py --project-root . update --task-id "$TID" --status in_progress --summary "wiring the engine" --tokens 1200 --skills-used writing-plans
python3 monitor/scripts/tasks.py --project-root . close --task-id "$TID" --status success --summary "done" --tokens 400 --credits 2.5 --cost 0.03
grep -c "task_id: $TID" monitor/tasks/tasks.mtr
```
Expected: prints an 8-char hex id, then `3` (one line per event — start/update/close each wrote a `task_id:` field line). The two `update`/`close` calls print a `warning: could not refresh Tasks page: No module named 'render_tasks'` to stderr — expected until Task 3.

- [ ] **Step 3: Verify validation rejects a terminal status on `update` and a non-terminal on `close`**

```bash
cd /tmp/monitor-task-test
python3 monitor/scripts/tasks.py --project-root . update --task-id "$TID" --status success --summary "bad" 2>&1 | grep -q "usage:" && echo "PASS: argparse choices rejected terminal status on update"
python3 monitor/scripts/tasks.py --project-root . close --task-id "$TID" --status open --summary "bad" 2>&1 | grep -q "usage:" && echo "PASS: argparse choices rejected non-terminal status on close"
python3 monitor/scripts/tasks.py --project-root . update --task-id doesnotexist --status open --summary "bad" 2>&1 | grep -q "unknown task_id" && echo "PASS: unknown task_id rejected"
```
Expected: all three `PASS` lines print.

- [ ] **Step 4: Commit**

```bash
cd /Users/ojaswi/Projects/monitor-tools
git add plugins/monitor/skills/monitor/scripts/tasks.py
git commit -m "feat: add tasks.py — start/update/close a lifecycle-tracked task"
```

---

### Task 3: `render_tasks.py` — render `monitor/tasks/*.html`, wire the third Dashboard tab

**Files:**
- Create: `plugins/monitor/skills/monitor/scripts/render_tasks.py`
- Modify: `plugins/monitor/skills/monitor/scripts/monitor_lib.py:299-307` (`tabnav()`)

**Interfaces:**
- Consumes: `tasks.mtr`'s on-disk format (Task 2, `render_entry()`'s exact field names). `mlib.tabnav(active, prefix)` (modified this task to accept `"tasks"`).
- Produces: `render_tasks.render(root: Path) -> Path` (writes paginated pages, returns the index path — mirrors `render_logs.render`). `render_tasks.parse_tasks(text: str) -> list[dict]`. `render_tasks.group_tasks(entries: list[dict]) -> list[dict]` (each group dict has keys `task_id, title, status, branch, tokens, credits, cost, skills_used, tools_called, events`). `render_tasks.count_open(root: Path) -> int` — consumed by `render_report.py` in Task 5 for the Dashboard KPI.

- [ ] **Step 1: Update `tabnav()` in `monitor_lib.py` for the third tab**

Replace lines 299-307:

```python
def tabnav(active: str, prefix: str) -> str:
    """Reports/Logs/Tasks tab-nav. `prefix` is the relative path back to
    monitor/. active is 'reports', 'logs', or 'tasks'."""
    def a(name, href, key):
        cls = ' class="active" aria-current="page"' if key == active else ''
        return f'<a href="{href}"{cls}>{name}</a>'
    return (f'<nav class="tabnav" aria-label="Dashboard pages">'
            f'{a("Reports", prefix + "reports/index.html", "reports")}'
            f'{a("Logs", prefix + "logs/index.html", "logs")}'
            f'{a("Tasks", prefix + "tasks/index.html", "tasks")}</nav>')
```

- [ ] **Step 2: Write `render_tasks.py`**

```python
#!/usr/bin/env python3
"""Render monitor/tasks/tasks.mtr into paginated monitor/tasks/*.html.

Groups task-start/task-update/task-close events by task_id into one card per
task: current status, aggregated metrics (tokens/credits/cost summed,
skills_used/tools_called unioned), and a collapsible oldest-to-newest
timeline. Called by tasks.py after every event; also runnable standalone.

Usage:  python3 render_tasks.py --project-root <repo>
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import monitor_lib as mlib

SEPARATOR = "=" * 80
_HEADER = re.compile(
    r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d+) (\w+) \[([^\]]*)\] \(([^)]*)\) (.*)$")
_PAGE_FILE_RE = re.compile(r"^page-(\d+)\.html$")

NONTERMINAL = ("open", "in_progress", "needs_approval", "needs_retry", "blocked")
TERMINAL = ("success", "failed", "cancelled")
STATUS_TAG_CLASS = {
    "open": "info", "in_progress": "info",
    "needs_approval": "warn", "needs_retry": "warn", "blocked": "warn",
    "success": "pass", "failed": "fail", "cancelled": "fail",
}


def parse_tasks(text: str) -> list[dict]:
    """Parse tasks.mtr into flat events, newest-first — one dict per
    task-start/task-update/task-close block. Tolerant the same way
    render_logs.parse_log is: an unparseable block is skipped with a stderr
    warning rather than corrupting the rest of the read."""
    entries: list[dict] = []
    for block in text.split("\n" + SEPARATOR + "\n"):
        block = block.strip("\n")
        if not block:
            continue
        lines = block.split("\n")
        m = _HEADER.match(lines[0])
        if not m:
            sys.stderr.write(f"render_tasks: WARNING skipped unparseable block: {lines[0]!r}\n")
            continue
        timestamp, level, event, task_id, rest = m.groups()
        summary, status = rest, ""
        if " -- " in rest:
            summary, status = rest.rsplit(" -- ", 1)
        e = {"timestamp": timestamp, "level": level, "event": event,
             "task_id": task_id, "summary": summary, "status": status,
             "title": "", "branch": "", "last_commit_hash": "",
             "tokens": None, "credits": None, "cost": None,
             "skills_used": [], "tools_called": [], "details": ""}
        for line in lines[1:]:
            if ":" not in line:
                continue
            key, val = line.split(":", 1)
            key, val = key.strip(), val.strip()
            if key == "title":
                e["title"] = val
            elif key == "branch":
                e["branch"] = val
            elif key == "last_commit_hash":
                e["last_commit_hash"] = val
            elif key in ("tokens", "credits", "cost"):
                try:
                    e[key] = float(val)
                except ValueError:
                    pass
            elif key == "skills_used":
                e["skills_used"] = [s.strip() for s in val.split(",") if s.strip()]
            elif key == "tools_called":
                e["tools_called"] = [t.strip() for t in val.split(",") if t.strip()]
            elif key == "details":
                e["details"] = val
        entries.append(e)
    return entries


def group_tasks(entries: list[dict]) -> list[dict]:
    """Group flat events (newest-first) by task_id. Each group's `status` is
    whichever event was encountered first per id (since the input is
    newest-first, that's the most recent event); `events` is collected then
    reversed to oldest-to-newest for timeline display."""
    groups: dict[str, dict] = {}
    order: list[str] = []
    for e in entries:
        tid = e["task_id"]
        if tid not in groups:
            groups[tid] = {"task_id": tid, "title": "", "status": e["status"],
                          "branch": e.get("branch", ""), "tokens": 0.0,
                          "credits": 0.0, "cost": 0.0, "skills_used": [],
                          "tools_called": [], "events": []}
            order.append(tid)
        g = groups[tid]
        g["events"].append(e)
        if e.get("title"):
            g["title"] = e["title"]
        if e.get("tokens") is not None:
            g["tokens"] += e["tokens"]
        if e.get("credits") is not None:
            g["credits"] += e["credits"]
        if e.get("cost") is not None:
            g["cost"] += e["cost"]
        for s in e.get("skills_used", []):
            if s not in g["skills_used"]:
                g["skills_used"].append(s)
        for t in e.get("tools_called", []):
            if t not in g["tools_called"]:
                g["tools_called"].append(t)
    result = [groups[tid] for tid in order]
    for g in result:
        g["events"].reverse()  # oldest-to-newest for the timeline
    return result


def count_open(root: Path) -> int:
    path = mlib.monitor_dir(root) / "tasks" / "tasks.mtr"
    if not path.exists():
        return 0
    entries = parse_tasks(path.read_text(encoding="utf-8"))
    groups = group_tasks(entries)
    return sum(1 for g in groups if g["status"] in NONTERMINAL)


def _card(g: dict) -> str:
    tag_cls = STATUS_TAG_CLASS.get(g["status"], "info")
    p = ['  <article class="logcard">', '    <div class="row">',
         f'      <span class="op">{mlib.esc(g["title"] or g["task_id"])}</span>',
         f'      <span class="toolchip">id: {mlib.esc(g["task_id"])}</span>']
    if g.get("branch"):
        p.append("      " + mlib.branch_chip(g["branch"]))
    p.append(f'      <span class="toolchip">tokens: {int(g["tokens"])}</span>')
    if g["credits"]:
        p.append(f'      <span class="toolchip">credits: {g["credits"]:g}</span>')
    if g["cost"]:
        p.append(f'      <span class="toolchip">cost: {g["cost"]:g}</span>')
    p.append('      <span class="spacer"></span>')
    p.append(f'      <span class="tag {tag_cls}">{mlib.esc(g["status"].upper())}</span>')
    p.append('    </div>')
    if g["skills_used"] or g["tools_called"]:
        chips = "".join(f'<span class="file">{mlib.esc(s)}</span>' for s in g["skills_used"] + g["tools_called"])
        p.append(f'    <div class="files">{chips}</div>')
    p += ['    <details>', '      <summary>Timeline</summary>']
    for e in g["events"]:
        p.append(f'      <p>{mlib.esc(e["timestamp"])} — <b>{mlib.esc(e["status"])}</b> — {mlib.esc(e["summary"])}</p>')
    p += ['    </details>', '  </article>']
    return "\n".join(p)


def build_html(page_groups: list[dict], brand: str, branch: str, *, total: int,
               n_open: int, page_num: int, total_pages: int) -> str:
    header = f"""  <header class="report">
    <h1>Tasks</h1>
    <p class="subtitle">Lifecycle-tracked units of work, newest first. Rendered from <code>monitor/tasks/tasks.mtr</code>.</p>
    {mlib.tabnav("tasks", "../")}
  </header>

  <div class="kpis">
    <div class="kpi"><div class="label">Current branch</div><div class="value small mono">{mlib.esc(branch or mlib.NO_BRANCH)}</div></div>
    <div class="kpi"><div class="label">Total tasks</div><div class="value">{total}</div></div>
    <div class="kpi warn"><div class="label">Open</div><div class="value">{n_open}</div></div>
  </div>"""
    if page_groups:
        body = '  <div class="log">\n' + "\n".join(_card(g) for g in page_groups) + "\n  </div>"
    else:
        body = '  <div class="empty">No tasks yet.</div>'
    body += "\n" + mlib.pagination_nav(page_num, total_pages, total)
    noun = "task" if total == 1 else "tasks"
    footer = (f'  <footer><span>Rendered from monitor/tasks/tasks.mtr · {total} {noun}.</span>'
              f'<span><a href="../index.html">← Dashboard</a> · <a href="#top">↑ Back to Top</a></span></footer>')
    title = "Tasks" if total_pages <= 1 else f"Tasks (page {page_num}/{total_pages})"
    return mlib.page(f"{title} — {brand} Monitor", brand, "info", "Monitor · Tasks",
                     header, body, footer, branch=branch)


def _prune_stale_pages(tasks_dir: Path, total_pages: int) -> None:
    for f in tasks_dir.glob("page-*.html"):
        m = _PAGE_FILE_RE.match(f.name)
        if m and int(m.group(1)) > total_pages:
            f.unlink()


def render(root: Path) -> Path:
    mdir = mlib.monitor_dir(root)
    tasks_dir = mdir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    tasks_path = tasks_dir / "tasks.mtr"
    text = tasks_path.read_text(encoding="utf-8") if tasks_path.exists() else ""
    profile = mlib.load_profile(root)
    brand = mlib.project_name(profile, root)
    branch = mlib.git_branch(root)

    entries = parse_tasks(text)
    groups = group_tasks(entries)
    total = len(groups)
    n_open = sum(1 for g in groups if g["status"] in NONTERMINAL)
    total_pages = max(1, -(-total // mlib.PAGE_SIZE))

    for page_num in range(1, total_pages + 1):
        start = (page_num - 1) * mlib.PAGE_SIZE
        page_groups = groups[start:start + mlib.PAGE_SIZE]
        html = build_html(page_groups, brand, branch, total=total, n_open=n_open,
                          page_num=page_num, total_pages=total_pages)
        (tasks_dir / mlib.page_filename(page_num)).write_text(html, encoding="utf-8")

    _prune_stale_pages(tasks_dir, total_pages)
    return tasks_dir / "index.html"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mlib.add_root_arg(ap)
    args = ap.parse_args()
    root = mlib.resolve_root(args)
    mlib.require_init(root)
    print(f"wrote {render(root)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Verify end-to-end with the tasks written in Task 2**

```bash
cd /tmp/monitor-task-test
cp /Users/ojaswi/Projects/monitor-tools/plugins/monitor/skills/monitor/scripts/render_tasks.py monitor/scripts/
cp /Users/ojaswi/Projects/monitor-tools/plugins/monitor/skills/monitor/scripts/monitor_lib.py monitor/scripts/
python3 monitor/scripts/render_tasks.py --project-root .
grep -q "Ship the tasks feature" monitor/tasks/index.html && echo "PASS: card title rendered"
grep -q "SUCCESS" monitor/tasks/index.html && echo "PASS: final status rendered"
grep -q "tokens: 1600" monitor/tasks/index.html && echo "PASS: metrics summed (1200 + 400)"
grep -qc 'class="tabnav"' monitor/tasks/index.html && grep -q ">Tasks<" monitor/tasks/index.html && echo "PASS: Tasks tab present"
```
Expected: all four `PASS` lines. (`1200 + 400 = 1600` from the `update`/`close` calls in Task 2 Step 2.)

- [ ] **Step 4: Commit**

```bash
cd /Users/ojaswi/Projects/monitor-tools
git add plugins/monitor/skills/monitor/scripts/render_tasks.py plugins/monitor/skills/monitor/scripts/monitor_lib.py
git commit -m "feat: add render_tasks.py, wire Tasks as the third Dashboard tab"
```

---

### Task 4: `logger.py` — swap free-text `--task` for `--task-id` foreign key

**Files:**
- Modify: `plugins/monitor/skills/monitor/scripts/logger.py`
- Modify: `plugins/monitor/skills/monitor/scripts/render_logs.py`

**Interfaces:**
- Produces: `logger.py`'s `log_operation()` gains `task_id=None` param (replacing `task=""`); `--task-id` CLI flag (replacing `--task`). `render_logs.py`'s parsed entry dicts gain `task_id` key (replacing `task`).

- [ ] **Step 1: Update `logger.py`**

In `log_operation()` (currently around line 80-98), change the signature and body:

```python
def log_operation(root: Path, *, operation, tool, summary, status,
                  level="INFO", details="", files=None, task_id=None, extra=None,
                  branch=None, last_commit_hash=None) -> None:
    if branch is None:
        branch = mlib.git_branch(root)
    if last_commit_hash is None:
        last_commit_hash = mlib.git_last_commit(root)
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3],
        "level": mlib.sanitize(level), "operation": mlib.sanitize(operation),
        "tool": mlib.sanitize(tool), "summary": mlib.sanitize(summary),
        "status": mlib.sanitize(status), "branch": mlib.sanitize(branch),
        "task_id": mlib.sanitize(task_id) if task_id else "",
        "details": mlib.sanitize(details),
        "files": [mlib.sanitize(f) for f in (files or [])],
        "extra": {mlib.sanitize(k): mlib.sanitize(v) for k, v in (extra or {}).items()},
        "last_commit_hash": mlib.sanitize(last_commit_hash),
    }
```

In `render_entry()`, replace:
```python
    if entry.get("task"):
        lines.append(f"task:    {entry['task']}")
```
with:
```python
    if entry.get("task_id"):
        lines.append(f"task_id: {entry['task_id']}")
```

In `main()`, replace the `ap.add_argument("--task", default="")` line with:
```python
    ap.add_argument("--task-id", dest="task_id", default=None,
                    help="Optional foreign key into monitor/tasks/tasks.mtr — "
                         "the task this log entry happened during.")
```
and in the `log_operation(...)` call inside `main()`, replace `task=args.task,` with `task_id=args.task_id,`.

- [ ] **Step 2: Update `render_logs.py`'s parser and card renderer**

In `parse_log()`'s per-entry default dict, replace `"task": ""` with `"task_id": ""`. In the field-parsing loop, replace:
```python
            elif key == "task":
                e["task"] = val
```
with:
```python
            elif key == "task_id":
                e["task_id"] = val
```

In `_card()`, replace the task paragraph block:
```python
    if e["task"]:
        p.append(f'    <p class="task"><b>Task</b> {mlib.esc(e["task"])}</p>')
```
with a chip alongside the existing `last_commit_hash` chip (insert right after the `last_commit_hash` chip block, before the `for k, v in e["extra"].items()` loop):
```python
    if e.get("task_id"):
        p.append(f'      <span class="toolchip">task: {mlib.esc(e["task_id"])}</span>')
```
Note this line moves from the card-body list (`p.append('    <p ...')`) into the row-chips list (alongside `branch`/`last_commit_hash`) — it must be added where the other `<span class="toolchip">` chips are built, inside the `<div class="row">`, not after `p.append('    </div>')`.

- [ ] **Step 3: Verify the swap**

```bash
cd /tmp/monitor-task-test
cp /Users/ojaswi/Projects/monitor-tools/plugins/monitor/skills/monitor/scripts/logger.py monitor/scripts/
cp /Users/ojaswi/Projects/monitor-tools/plugins/monitor/skills/monitor/scripts/render_logs.py monitor/scripts/
python3 monitor/scripts/logger.py --project-root . --operation link-test --tool Bash --summary "linked to a task" --status success --task-id "$TID"
grep -q "task_id: $TID" monitor/logs/operations.mtr && echo "PASS: task_id written to operations.mtr"
python3 monitor/scripts/render_logs.py --project-root .
grep -q "task: $TID" monitor/logs/index.html && echo "PASS: task_id chip rendered on Logs page"
python3 monitor/scripts/logger.py --project-root . --operation no-task --tool Bash --summary "no task" --status success 2>&1
echo "exit: $?"
```
Expected: both `PASS` lines, and the last `logger.py` call (no `--task-id`) exits 0 with no error — confirms the field stays fully optional.

- [ ] **Step 4: Commit**

```bash
cd /Users/ojaswi/Projects/monitor-tools
git add plugins/monitor/skills/monitor/scripts/logger.py plugins/monitor/skills/monitor/scripts/render_logs.py
git commit -m "feat: replace logger.py's free-text --task with a --task-id foreign key into tasks.mtr"
```

---

### Task 5: Dashboard "Open tasks" KPI + `clean.py --tasks`

**Files:**
- Modify: `plugins/monitor/skills/monitor/scripts/render_report.py` (`render_dashboard`, `refresh_dashboard`, `render_all`)
- Modify: `plugins/monitor/skills/monitor/scripts/clean.py`

**Interfaces:**
- Consumes: `render_tasks.count_open(root) -> int` (Task 3).
- Produces: `render_report.render_dashboard()` gains an `n_open_tasks` parameter; `clean.py` gains `clean_tasks(root, n, dry) -> int` and a `--tasks` CLI flag.

- [ ] **Step 1: Update `render_report.py`**

Add the import near the top (with the existing `import render_logs`):
```python
import render_tasks
```

Update `render_dashboard()`'s signature and body (currently lines 289-316):
```python
def render_dashboard(profile: dict, n_reports: int, root: Path,
                     branch: str = "") -> None:
    brand = mlib.project_name(profile, root)
    mdir = mlib.monitor_dir(root)
    log_path = mdir / "logs" / "operations.mtr"
    n_logs = len([e for e in render_logs.parse_log(log_path.read_text(encoding="utf-8"))
                  if e.get("fragment") is None]) if log_path.exists() else 0
    n_open_tasks = render_tasks.count_open(root)
    header = f"""  <header class="report">
    <h1>{mlib.esc(brand)} · Monitor</h1>
    <p class="subtitle">Reports, logs, and tasks for this project's agent workflow.</p>
    {mlib.tabnav("", "")}
  </header>

  <div class="kpis">
    <div class="kpi"><div class="label">Current branch</div><div class="value small mono">{mlib.esc(branch or mlib.NO_BRANCH)}</div></div>
    <div class="kpi"><div class="label">Reports</div><div class="value">{n_reports}</div></div>
    <div class="kpi"><div class="label">Log entries</div><div class="value">{n_logs}</div></div>
    <div class="kpi warn"><div class="label">Open tasks</div><div class="value">{n_open_tasks}</div></div>
    <div class="kpi"><div class="label">Profile</div><div class="value small mono">v{profile.get("profileVersion", 1)}</div></div>
  </div>"""
    body = """  <div class="card-grid">
    <a class="navcard" href="reports/index.html"><h3>Reports →</h3><p>Task and change reports, newest first.</p></a>
    <a class="navcard" href="logs/index.html"><h3>Logs →</h3><p>Every logged operation with status and details.</p></a>
    <a class="navcard" href="tasks/index.html"><h3>Tasks →</h3><p>Lifecycle-tracked units of work with self-reported metrics.</p></a>
  </div>"""
    footer = ('  <footer><span>monitor · project dashboard</span>'
              '<span><a href="#top">↑ Back to Top</a></span></footer>')
    out = mlib.page(f"{brand} · Monitor", brand, "info", "Monitor", header, body,
                    footer, branch=branch)
    (mdir / "index.html").write_text(out, encoding="utf-8")
```
(This is a full replacement of the existing function body — the only *logic* addition is the `n_open_tasks` line and its KPI div; the rest is copied verbatim from the current file with the two body/subtitle string tweaks shown.)

`render_all()` (around line 333-342) needs no signature change — it already calls `render_dashboard(profile, len(items), root, branch)`, and `mdir / "tasks"` should also be ensured to exist alongside `reports`/`logs`. Add one line:
```python
    (mdir / "tasks").mkdir(parents=True, exist_ok=True)
```
right after the existing `(mdir / "logs").mkdir(parents=True, exist_ok=True)` line.

- [ ] **Step 2: Update `clean.py`**

Add near the top (with the existing `import render_logs` / `import render_report`):
```python
import render_tasks
```

Add a new function after `clean_reports()`:
```python
def clean_tasks(root: Path, n: int, dry: bool) -> int:
    tasks_path = mlib.monitor_dir(root) / "tasks" / "tasks.mtr"
    if not tasks_path.exists():
        print("no tasks.mtr")
        return 0
    text = tasks_path.read_text(encoding="utf-8")
    entries = render_tasks.parse_tasks(text)
    groups = render_tasks.group_tasks(entries)  # newest-first by task
    n = max(0, min(n, len(groups)))
    to_remove = {g["task_id"] for g in groups[len(groups) - n:]}
    print(f"removing {n} oldest of {len(groups)} tasks (all their events)")
    if dry:
        return 0
    blocks = [b for b in text.split(SEPARATOR + "\n") if b.strip("\n")]
    kept_blocks = [b for b in blocks if not any(f"task_id: {tid}" in b for tid in to_remove)]
    new_text = "".join(b + SEPARATOR + "\n" for b in kept_blocks)
    tasks_path.write_text(new_text, encoding="utf-8")
    render_tasks.render(root)
    return 0
```

Update `main()`: add `ap.add_argument("--tasks", type=int, help="Delete the oldest N tasks (all their events)")` next to the existing `--logs`/`--reports` args, and add:
```python
    if args.tasks is not None:
        return clean_tasks(root, args.tasks, args.dry_run)
```
before the final `ap.error(...)` line. Update that final line's message to `"one of --logs, --reports, or --tasks is required"`.

- [ ] **Step 3: Verify the KPI and clean-tasks**

```bash
cd /tmp/monitor-task-test
cp /Users/ojaswi/Projects/monitor-tools/plugins/monitor/skills/monitor/scripts/render_report.py monitor/scripts/
cp /Users/ojaswi/Projects/monitor-tools/plugins/monitor/skills/monitor/scripts/clean.py monitor/scripts/
python3 monitor/scripts/render_report.py --project-root .
grep -q "Open tasks" monitor/index.html && echo "PASS: KPI label present"
grep -A2 "Open tasks" monitor/index.html | grep -q '"value">0<' && echo "PASS: 0 open (the only task is closed/success)"
python3 monitor/scripts/clean.py --project-root . --tasks 1 --dry-run
python3 monitor/scripts/clean.py --project-root . --tasks 1
grep -q "$TID" monitor/tasks/tasks.mtr && echo "FAIL: task not removed" || echo "PASS: task fully removed"
```
Expected: three `PASS` lines, no `FAIL`.

- [ ] **Step 4: Commit**

```bash
cd /Users/ojaswi/Projects/monitor-tools
git add plugins/monitor/skills/monitor/scripts/render_report.py plugins/monitor/skills/monitor/scripts/clean.py
git commit -m "feat: add Open tasks Dashboard KPI and clean.py --tasks"
```

---

### Task 6: Commands + `SKILL.md` documentation

**Files:**
- Create: `plugins/monitor/commands/task-start.md`
- Create: `plugins/monitor/commands/task-update.md`
- Create: `plugins/monitor/commands/task-close.md`
- Modify: `plugins/monitor/skills/monitor/SKILL.md`
- Modify: `plugins/monitor/.claude-plugin/plugin.json` (version bump)

**Interfaces:**
- Consumes: `tasks.py`'s CLI (Task 2).

- [ ] **Step 1: Write `plugins/monitor/commands/task-start.md`**

```markdown
---
description: Start a new lifecycle-tracked task.
---

Start a monitor task for: **$ARGUMENTS**

**PRECONDITION — monitor must be initialised (check this FIRST).**
Verify `monitor/profile.json` exists (`test -f monitor/profile.json`). If it does
**not** exist, do **not** run any engine script or take any action. Reply with
exactly —

> ⚠️ monitor isn't initialised for this project yet. Run `/monitor:init` first, then re-run this command.

— and then STOP (end your turn immediately). Do not continue past this gate.

Read the **monitor** skill (`SKILL.md`) first, specifically the "Tasks"
section. Then start the task via the engine:

```
python3 monitor/scripts/tasks.py --project-root . start --title "<short title>" \
    [--status open] [--summary "..."] [--tokens N] [--credits N] [--cost N] \
    [--skills-used a b] [--tools-called a b] [--details "..."]
```

The command prints the generated `task_id` (an 8-character id) — **relay it
to the user prominently and remember it for this session**: every
`/monitor:task-update` and `/monitor:task-close` call for this task needs it,
and log entries made while working on it can carry it via `logger.py
--task-id <id>` to cross-reference. Status defaults to `open`; use `--status
in_progress` if work starts immediately.
```

- [ ] **Step 2: Write `plugins/monitor/commands/task-update.md`**

```markdown
---
description: Update a task's status and/or metrics mid-flight.
---

Update monitor task: **$ARGUMENTS**

**PRECONDITION — monitor must be initialised (check this FIRST).**
Verify `monitor/profile.json` exists (`test -f monitor/profile.json`). If it does
**not** exist, do **not** run any engine script or take any action. Reply with
exactly —

> ⚠️ monitor isn't initialised for this project yet. Run `/monitor:init` first, then re-run this command.

— and then STOP (end your turn immediately). Do not continue past this gate.

Read the **monitor** skill (`SKILL.md`) first, specifically the "Tasks"
section. `$ARGUMENTS` should identify the task (by its id, given when it was
started) and what changed. Then update it via the engine:

```
python3 monitor/scripts/tasks.py --project-root . update --task-id <id> \
    --status open|in_progress|needs_approval|needs_retry|blocked \
    --summary "<what changed>" [--tokens N] [--credits N] [--cost N] \
    [--skills-used a b] [--tools-called a b] [--details "..."]
```

`--status` must be one of the **non-terminal** values above — use
`/monitor:task-close` for a final success/failed/cancelled outcome. Metrics
passed here are additive: they accumulate on top of whatever the task
already has, they don't replace the running total.
```

- [ ] **Step 3: Write `plugins/monitor/commands/task-close.md`**

```markdown
---
description: Close a task with its final outcome.
---

Close monitor task: **$ARGUMENTS**

**PRECONDITION — monitor must be initialised (check this FIRST).**
Verify `monitor/profile.json` exists (`test -f monitor/profile.json`). If it does
**not** exist, do **not** run any engine script or take any action. Reply with
exactly —

> ⚠️ monitor isn't initialised for this project yet. Run `/monitor:init` first, then re-run this command.

— and then STOP (end your turn immediately). Do not continue past this gate.

Read the **monitor** skill (`SKILL.md`) first, specifically the "Tasks"
section. `$ARGUMENTS` should identify the task (by its id) and its outcome.
Then close it via the engine:

```
python3 monitor/scripts/tasks.py --project-root . close --task-id <id> \
    --status success|failed|cancelled --summary "<final outcome>" \
    [--tokens N] [--credits N] [--cost N] [--skills-used a b] \
    [--tools-called a b] [--details "..."]
```

`--status` must be one of the **terminal** values above — use
`/monitor:task-update` for anything still in progress. Once closed, don't
issue further update/close calls for the same `task_id`; start a new task if
more work on the same topic comes up later.
```

- [ ] **Step 4: Add the `## Tasks` section to `SKILL.md`**

Insert a new section right after the existing `## Reporting` section (after
line 203, before `## Memory`):

```markdown
## Tasks
A third tracked entity, separate from logs and reports: a lifecycle-tracked
unit of work with self-reported metrics, backed by `monitor/tasks/tasks.mtr`
(same append-only block format as `operations.mtr`) and rendered to a
paginated `monitor/tasks/index.html`, linked as the third Dashboard tab.

- **Lifecycle:** `open → in_progress → (needs_approval | needs_retry |
  blocked)* → success | failed | cancelled`. The first 5 are non-terminal
  (valid on `/monitor:task-start`/`/monitor:task-update`); the last 3 are
  terminal (valid only on `/monitor:task-close`).
- **Metrics are self-reported, not instrumented.** `tokens`, `credits`,
  `cost`, `skills_used`, `tools_called` are CLI flags the agent fills in
  from its own knowledge of what it did — the engine is stdlib Python with
  no access to the real session transcript, so it cannot introspect actual
  token counts or which skills/tools actually ran. Same trust model
  `--details` already uses.
- **Metrics accumulate.** Every `task-update`/`task-close` call's numeric
  metrics add to the task's running total; `skills_used`/`tools_called`
  union (dedup) across calls.
- **Log entries can reference a task.** `logger.py --task-id <id>` stores a
  foreign key into `tasks.mtr` on that log entry, rendered as a chip on the
  Logs page — purely a cross-reference, not required.
- **Commands:** `/monitor:task-start "<title>"` (returns and prints the
  generated `task_id` — relay it to the user, you need it for every
  subsequent call), `/monitor:task-update <id> --status ...`,
  `/monitor:task-close <id> --status success|failed|cancelled`.

### Integration points
- This harness's own `TaskCreate`/`TaskUpdate`/`TaskGet` calls map naturally
  onto `task-start`/`task-update`/`task-close` — when already tracking a
  task with the harness's native tool, mirror the same lifecycle into
  monitor so it's recoverable from the log/report system too, not just the
  harness's own ephemeral task state.
- `superpowers:subagent-driven-development`'s per-task dispatch loop
  (ledger file, one task per implementer round) maps the same way: a
  `task-start` when a task's implementer is dispatched, `task-update` on
  each fix-loop round, `task-close` when the ledger marks it done.
```

Also update the `## Where things live` tree (around line 22-29) to add the
new folder — insert `tasks/    tasks.mtr  index.html` as a new line right
after the `logs/     operations.mtr  index.html` line.

Also add one row to the `## Common mistakes` table (around line 218-225):
```markdown
| Putting task info in `--details` on a log entry | Tasks are a separate tracked entity now, not a log field. Use `/monitor:task-start`/`update`/`close`; cross-reference with `logger.py --task-id`. |
```

- [ ] **Step 5: Bump the plugin version**

In `plugins/monitor/.claude-plugin/plugin.json`, bump `"version"` from
`"1.11.2"` to `"1.12.0"` (minor bump — new feature, not a fix) and append
one sentence to the end of the `"description"` field: `" A third tracked
entity, tasks (monitor/tasks/tasks.mtr), records lifecycle-tracked units of
work with self-reported token/credit/cost metrics, alongside logs and
reports."`

- [ ] **Step 6: Verify commands parse and the full scratch-project flow works end to end**

```bash
cd /tmp/monitor-task-test
python3 -c "
import re
for f in ['task-start.md','task-update.md','task-close.md']:
    pass
"
for f in /Users/ojaswi/Projects/monitor-tools/plugins/monitor/commands/task-*.md; do
  python3 -c "
import sys
text = open('$f').read()
assert text.startswith('---'), '$f missing frontmatter'
assert 'description:' in text.splitlines()[1], '$f missing description'
assert 'PRECONDITION' in text, '$f missing init gate'
print('PASS: $f well-formed')
"
done
grep -q "## Tasks" /Users/ojaswi/Projects/monitor-tools/plugins/monitor/skills/monitor/SKILL.md && echo "PASS: SKILL.md has Tasks section"
python3 -c "import json; d=json.load(open('/Users/ojaswi/Projects/monitor-tools/plugins/monitor/.claude-plugin/plugin.json')); assert d['version']=='1.12.0'; print('PASS: version bumped')"
```
Expected: `PASS` for each of the 3 command files, plus the SKILL.md and version checks — 5 `PASS` lines total, no assertion errors.

- [ ] **Step 7: Clean up the scratch test directory**

```bash
rm -rf /tmp/monitor-task-test
```

- [ ] **Step 8: Commit**

```bash
cd /Users/ojaswi/Projects/monitor-tools
git add plugins/monitor/commands/task-start.md plugins/monitor/commands/task-update.md \
        plugins/monitor/commands/task-close.md plugins/monitor/skills/monitor/SKILL.md \
        plugins/monitor/.claude-plugin/plugin.json
git commit -m "feat: add /monitor:task-start|update|close commands, document Tasks in SKILL.md, bump to 1.12.0"
```

---

## Self-Review Notes

**Spec coverage:** every section of `docs/superpowers/specs/2026-07-26-tasks-feature-design.md` maps to a task — data model & status enum (Task 2), engine (`tasks.py`, Task 2), render script (Task 3), logger decoupling (Task 4), Dashboard/clean.py (Task 5), commands + SKILL.md + integration points (Task 6). The spec's explicit non-goals (no pending-gate integration, no new companion plugin) are respected — no task touches `pending.py`.

**Type/signature consistency:** `task_id` is the field name used consistently across `tasks.py`, `render_tasks.py`, `logger.py`, and `render_logs.py` — no `task` vs `taskId` vs `task_id` drift. `STATUSES`/`NONTERMINAL`/`TERMINAL` are defined identically (same tuple values) in both `tasks.py` and `render_tasks.py` since they're separate processes reading the same file format — duplicated intentionally rather than cross-imported, matching this codebase's existing pattern of each script being independently runnable.

**No placeholders:** every step has real, complete code — no "add validation" or "similar to Task N" hand-waving.
