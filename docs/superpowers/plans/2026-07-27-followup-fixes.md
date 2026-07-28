# Follow-up Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship all seven follow-up items from `docs/superpowers/specs/2026-07-27-followup-fixes-design.md`: open-task pending-gate coverage, `clean --tasks` creation-order fix, a pytest test suite (+ `test-unit`/`test-integration` skills), report+task search coverage (+ a Dashboard grep box), report `date_created`/`last_modified` timestamps, a `test-thought-leaks` skill, and a `test-automated` orchestration skill.

**Architecture:** Nine tasks, each independently testable. Tasks 1-2 are small engine fixes (`pending.py`, `render_tasks.py`/`clean.py`). Tasks 3-4 build the pytest suite and its two wrapping skills. Tasks 5-6 extend `search.py` and add the Dashboard's client-side search. Task 7 is the report-template timestamp addition. Tasks 8-9 build `test-thought-leaks` and `test-automated`. Later tasks (4, 9) depend on earlier ones (3, 8) existing.

**Tech Stack:** Python 3 stdlib for the engine (unchanged constraint); pytest (dev-only, new `requirements-dev.txt`) for the new test suite; vanilla JS (no libraries) for the one Dashboard search feature.

## Global Constraints

- The shipped engine (`plugins/monitor/skills/monitor/scripts/*.py`) stays stdlib-only — no new imports there. `requirements-dev.txt` is a repo-root, dev-only file; nothing in `plugins/monitor/` or `install-monitor.sh` references it.
- Every engine script still resolves its root via `mlib.resolve_root(args)` and calls `mlib.require_init(root)` before doing anything else, except the parts that already run pre-init (hook entrypoints check `_monitor_initialized()` themselves).
- Status enum stays fixed: `open, in_progress, needs_approval, needs_retry, blocked` (non-terminal) / `success, failed, cancelled` (terminal).
- Reports are immutable snapshots — `date_created`/`last_modified` are stamped once at authoring/lock time, never rewritten afterward.
- The Dashboard's new `<script>` block is the *only* narrow exception to monitor's no-JS rule — Logs, Reports, Tasks pages, and the report template all stay script-free.
- Skill names stay flat kebab-case (`test-unit`, `test-integration`, `test-thought-leaks`, `test-automated`) — no colon namespacing (that requires real plugin packaging, out of scope).
- After changing `plugins/monitor/skills/monitor/`, bump `version` in `plugins/monitor/.claude-plugin/plugin.json`.
- All work happens on branch `feat/followup-fixes` (already checked out, forked from `dev`).

---

### Task 1: Open tasks feed the pending-hook gate

**Files:**
- Modify: `plugins/monitor/skills/monitor/scripts/pending.py`

**Interfaces:**
- Consumes: `render_tasks.parse_tasks(text) -> list[dict]`, `render_tasks.group_tasks(entries) -> list[dict]`, `render_tasks.NONTERMINAL` tuple (all exist in `render_tasks.py`).
- Produces: `pending.open_tasks(root: Path) -> list[dict]` (each dict has `task_id`, `title`, `status`) — consumed by `check_text()` in this same task, and reusable by Task 3's tests.

- [ ] **Step 1: Write the failing unit test (placed now, run once Task 3's suite scaffolding exists — for this task, verify manually first per Step 3 below; the permanent test moves into `tests/unit/test_pending.py` in Task 3)**

Manual verification script (run directly, not via pytest — Task 3 doesn't exist yet):
```bash
python3 - <<'EOF'
import subprocess, sys, tempfile
from pathlib import Path
tmp = Path(tempfile.mkdtemp())
engine = Path("plugins/monitor/skills/monitor/scripts")
scripts = tmp / "monitor" / "scripts"
scripts.mkdir(parents=True)
for f in engine.glob("*.py"):
    (scripts / f.name).write_text(f.read_text())
subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
subprocess.run(["git", "config", "user.email", "t@t.t"], cwd=tmp, check=True)
subprocess.run(["git", "config", "user.name", "t"], cwd=tmp, check=True)
subprocess.run([sys.executable, str(scripts / "profile.py"), "--project-root", str(tmp)], check=True)
subprocess.run([sys.executable, str(scripts / "tasks.py"), "--project-root", str(tmp),
                "start", "--title", "demo task"], check=True)
out = subprocess.run([sys.executable, str(scripts / "pending.py"), "--project-root", str(tmp), "check"],
                     capture_output=True, text=True)
assert "demo task" in out.stdout, f"expected open task in pending check output, got: {out.stdout!r}"
print("PASS: open task surfaces in pending check")
EOF
```

- [ ] **Step 2: Run it to confirm it currently fails**

Expected: `AssertionError: expected open task in pending check output, got: ''` (today's `check_text()` only reports logs/report, never tasks).

- [ ] **Step 3: Implement `open_tasks()` and wire it into `check_text()`**

Add to `pending.py`, after `_pending_phrase()` (before `check_text()`):
```python
def open_tasks(root: Path) -> list[dict]:
    """Every task whose most-recent status is non-terminal, i.e. still open."""
    try:
        import render_tasks
    except Exception:  # noqa: BLE001 — render_tasks.py should always be a
        return []       # sibling file, but never let this crash the hook
    path = mlib.monitor_dir(root) / "tasks" / "tasks.mtr"
    if not path.exists():
        return []
    entries = render_tasks.parse_tasks(path.read_text(encoding="utf-8"))
    groups = render_tasks.group_tasks(entries)
    return [{"task_id": g["task_id"], "title": g["title"], "status": g["status"]}
            for g in groups if g["status"] in render_tasks.NONTERMINAL]
```

Replace `_pending_phrase()` and `check_text()`:
```python
def _pending_phrase(data: dict, n_open_tasks: int) -> str:
    """"logs", "report", "N open task(s)", or a joined combination — only
    what is really pending."""
    parts = []
    if data.get("pending_logs"):
        parts.append("logs")
    if data.get("pending_report"):
        parts.append("report")
    if n_open_tasks:
        parts.append(f"{n_open_tasks} open task{'s' if n_open_tasks != 1 else ''}")
    return " and ".join(parts)


def check_text(root: Path) -> str:
    data = load_pending(root)
    tasks = open_tasks(root)
    phrase = _pending_phrase(data, len(tasks))
    if not phrase:
        return ""
    lines = [f"[Warn!] Monitor: Pending {phrase}. Do you want Monitor to "
             f"record now [Y/N]", "", INSTRUCTIONS]
    if tasks:
        task_lines = "\n".join(
            f"  - {t['task_id']}  ({t['status']})  {t['title']}" for t in tasks)
        lines.append("\nOpen tasks (close with /monitor:task-close when done, "
                     "or leave open and continue — this is informational, "
                     "not blocking):\n" + task_lines)
    return "\n".join(lines)
```

Note: `WARNING` (the module-level constant near line 153) still references the old fixed 2-part phrasing — leave it as documentation-only (it's already commented as "kept for callers/tests that import it," not the real runtime path); `check_text()` is what actually runs.

- [ ] **Step 4: Re-run the manual verification script from Step 1, confirm it passes**

Expected: `PASS: open task surfaces in pending check`

- [ ] **Step 5: Commit**

```bash
cd /Users/ojaswi/Projects/monitor-tools
git add plugins/monitor/skills/monitor/scripts/pending.py
git commit -m "feat: surface open tasks in the pending-state hook gate"
```

---

### Task 2: `clean --tasks` sorts by real creation time

**Files:**
- Modify: `plugins/monitor/skills/monitor/scripts/render_tasks.py`
- Modify: `plugins/monitor/skills/monitor/scripts/clean.py`

**Interfaces:**
- Produces: `render_tasks.group_tasks()`'s returned dicts gain a `created_at` key (the `task-start` event's timestamp string, or the earliest known event's timestamp if `task-start` isn't present in the retained window). Consumed by `clean.clean_tasks()`.

- [ ] **Step 1: Manual verification script showing today's wrong order**

```bash
python3 - <<'EOF'
import subprocess, sys, tempfile, time
from pathlib import Path
tmp = Path(tempfile.mkdtemp())
engine = Path("plugins/monitor/skills/monitor/scripts")
scripts = tmp / "monitor" / "scripts"
scripts.mkdir(parents=True)
for f in engine.glob("*.py"):
    (scripts / f.name).write_text(f.read_text())
subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
subprocess.run(["git", "config", "user.email", "t@t.t"], cwd=tmp, check=True)
subprocess.run(["git", "config", "user.name", "t"], cwd=tmp, check=True)
py = sys.executable
subprocess.run([py, str(scripts / "profile.py"), "--project-root", str(tmp)], check=True)
# Task A: started first (really oldest), but will be updated again later.
r = subprocess.run([py, str(scripts / "tasks.py"), "--project-root", str(tmp),
                    "start", "--title", "Task A (really oldest)"], capture_output=True, text=True, check=True)
a_id = r.stdout.split(":")[1].strip().split()[0]
time.sleep(1.1)
# Task B: started second (really newest, never touched again).
r = subprocess.run([py, str(scripts / "tasks.py"), "--project-root", str(tmp),
                    "start", "--title", "Task B (really newest)"], capture_output=True, text=True, check=True)
time.sleep(1.1)
# Touch Task A again — it's now "most recently active" despite being oldest.
subprocess.run([py, str(scripts / "tasks.py"), "--project-root", str(tmp),
                "update", "--task-id", a_id, "--status", "in_progress",
                "--summary", "still going"], check=True)
# Clean the oldest 1 — should remove Task A (created first), not Task B.
out = subprocess.run([py, str(scripts / "clean.py"), "--project-root", str(tmp),
                      "--tasks", "1", "--dry-run"], capture_output=True, text=True)
print(out.stdout)
assert "Task A" in out.stdout, f"expected Task A (oldest by creation) to be the one removed, got: {out.stdout!r}"
print("PASS: clean --tasks removes by creation order")
EOF
```

- [ ] **Step 2: Run it, confirm it currently fails**

Expected: the dry-run currently reports removing "Task B" (last-touched-first ordering means A, having been updated most recently, looks newest) — assertion fails.

- [ ] **Step 3: Add `created_at` tracking to `group_tasks()`**

Replace `group_tasks()` in `render_tasks.py`:
```python
def group_tasks(entries: list[dict]) -> list[dict]:
    """Group flat events (newest-first) by task_id. Each group's `status` is
    whichever event was encountered first per id (since the input is
    newest-first, that's the most recent event); `created_at` is the
    timestamp of its task-start event specifically (falling back to the
    earliest event seen for that id, if task-start isn't in the retained
    window); `events` is collected then reversed to oldest-to-newest for
    timeline display."""
    groups: dict[str, dict] = {}
    order: list[str] = []
    for e in entries:
        tid = e["task_id"]
        if tid not in groups:
            groups[tid] = {"task_id": tid, "title": "", "status": e["status"],
                          "branch": e.get("branch", ""), "tokens": 0.0,
                          "has_tokens": False, "credits": 0.0, "cost": 0.0,
                          "skills_used": [], "tools_called": [], "events": [],
                          "created_at": e["timestamp"]}
            order.append(tid)
        g = groups[tid]
        g["events"].append(e)
        if e.get("title"):
            g["title"] = e["title"]
        if e["event"] == "task-start" or e["timestamp"] < g["created_at"]:
            g["created_at"] = e["timestamp"]
        if e.get("tokens") is not None:
            # Tracked separately from the sum so a task that reported
            # `--tokens 0` still shows a tokens chip, and one that never
            # reported tokens at all shows none — same rule as credits/cost.
            g["tokens"] += e["tokens"]
            g["has_tokens"] = True
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
```
(Only the new `created_at` init/update lines and the docstring changed — everything else is byte-identical to the current function.)

- [ ] **Step 4: Sort by `created_at` in `clean_tasks()`**

In `clean.py`, replace the `clean_tasks()` body's group-selection lines:
```python
    text = tasks_path.read_text(encoding="utf-8")
    entries = render_tasks.parse_tasks(text)
    groups = render_tasks.group_tasks(entries)
    groups.sort(key=lambda g: g["created_at"])  # ascending: real oldest first
    n = max(0, min(n, len(groups)))
    removed = groups[:n]
    to_remove = {g["task_id"] for g in removed}
```
(This replaces the old `groups = render_tasks.group_tasks(entries)  # newest-first by task` / `removed = groups[len(groups) - n:]` pair — the explicit sort makes `removed = groups[:n]` correct regardless of `group_tasks()`'s own default order.)

- [ ] **Step 5: Re-run the Step 1 script, confirm it passes**

Expected: `PASS: clean --tasks removes by creation order`

- [ ] **Step 6: Commit**

```bash
cd /Users/ojaswi/Projects/monitor-tools
git add plugins/monitor/skills/monitor/scripts/render_tasks.py plugins/monitor/skills/monitor/scripts/clean.py
git commit -m "fix: clean --tasks sorts oldest-N by real creation time, not last activity"
```

---

### Task 3: pytest test suite (`tests/unit/`, `tests/integration/`, `conftest.py`)

**Files:**
- Create: `requirements-dev.txt`
- Create: `tests/conftest.py`
- Create: `tests/unit/test_sanitize.py`
- Create: `tests/unit/test_tasks.py`
- Create: `tests/unit/test_render_tasks.py`
- Create: `tests/unit/test_pending.py`
- Create: `tests/unit/test_clean.py`
- Create: `tests/integration/test_task_lifecycle_flow.py`
- Create: `tests/integration/test_pending_hook_flow.py`

**Interfaces:**
- Consumes: every engine script's public functions as already documented in Tasks 1-2 above and the existing codebase (`tasks.py`, `render_tasks.py`, `pending.py`, `clean.py`, `monitor_lib.py`).
- Produces: `tests/conftest.py`'s `project_root` fixture (a `pytest.fixture` yielding a `Path` to a freshly initialized scratch project with the engine copied in and `sys.path` set up for `import tasks`, `import pending`, etc.) — consumed by every test file in this task and by Task 5's/Task 6's tests in later tasks.

- [ ] **Step 1: Write `requirements-dev.txt`**

```
pytest>=8
```

- [ ] **Step 2: Write `tests/conftest.py`**

```python
"""Shared fixtures for the monitor engine's pytest suite. Every test runs
against a fresh tmp_path project root — never this repo's own real
monitor/ directory."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ENGINE_DIR = Path(__file__).resolve().parent.parent / "plugins" / "monitor" / "skills" / "monitor" / "scripts"


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    """A fresh scratch project: engine copied into monitor/scripts/, a real
    git repo (tasks/logger record commit shas and branch), and
    monitor/profile.json seeded via profile.py. Yields the project root."""
    scripts = tmp_path / "monitor" / "scripts"
    scripts.mkdir(parents=True)
    for f in ENGINE_DIR.glob("*.py"):
        (scripts / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=tmp_path, check=True)
    subprocess.run([sys.executable, str(scripts / "profile.py"),
                    "--project-root", str(tmp_path)], check=True, capture_output=True)
    sys.path.insert(0, str(scripts))
    yield tmp_path
    sys.path.remove(str(scripts))
    # Drop the modules so the next test's project_root re-imports fresh
    # copies pointed at its own tmp_path, not a stale cached module.
    for mod in ("tasks", "pending", "clean", "logger", "search",
               "render_tasks", "render_logs", "render_report", "monitor_lib"):
        sys.modules.pop(mod, None)
```

- [ ] **Step 3: Write `tests/unit/test_sanitize.py`**

```python
import monitor_lib as mlib


def test_sanitize_strips_control_chars():
    assert mlib.sanitize("hello\x00\x1bworld") == "helloworld"


def test_sanitize_flattens_real_newlines():
    assert mlib.sanitize("line one\nline two\r\nline three") == "line one line two line three"


def test_sanitize_trims_whitespace():
    assert mlib.sanitize("  padded  ") == "padded"


def test_sanitize_none_passes_through():
    assert mlib.sanitize(None) is None
```

- [ ] **Step 4: Run it, confirm it fails only on import path (no `project_root` fixture use yet — these three don't need the fixture, but confirm collection works)**

Run: `pip install -r requirements-dev.txt -q && PYTHONPATH=plugins/monitor/skills/monitor/scripts pytest tests/unit/test_sanitize.py -v`
Expected: 4 passed (this module needs no fixture since `mlib` is stdlib-only logic — this step just confirms the harness itself is wired correctly before building on it).

- [ ] **Step 5: Write `tests/unit/test_tasks.py`**

```python
import pytest

import tasks


def test_start_task_returns_id_and_writes_block(project_root):
    task_id = tasks.start_task(project_root, title="Demo task")
    text = (project_root / "monitor" / "tasks" / "tasks.mtr").read_text()
    assert f"task_id: {task_id}" in text
    assert "title:   Demo task" in text


def test_update_rejects_terminal_status(project_root):
    task_id = tasks.start_task(project_root, title="Demo task")
    with pytest.raises(ValueError, match="requires a non-terminal status"):
        tasks.update_task(project_root, task_id=task_id, status="success", summary="bad")


def test_close_rejects_nonterminal_status(project_root):
    task_id = tasks.start_task(project_root, title="Demo task")
    with pytest.raises(ValueError, match="requires a terminal status"):
        tasks.close_task(project_root, task_id=task_id, status="open", summary="bad")


def test_update_unknown_task_id_rejected(project_root):
    with pytest.raises(ValueError, match="unknown task_id"):
        tasks.update_task(project_root, task_id="doesnotexist", status="open", summary="x")


def test_metrics_accumulate_across_events(project_root):
    task_id = tasks.start_task(project_root, title="Demo", tokens=100)
    tasks.update_task(project_root, task_id=task_id, status="in_progress",
                      summary="more work", tokens=50)
    tasks.close_task(project_root, task_id=task_id, status="success",
                     summary="done", tokens=25)
    import render_tasks
    text = (project_root / "monitor" / "tasks" / "tasks.mtr").read_text()
    groups = render_tasks.group_tasks(render_tasks.parse_tasks(text))
    assert groups[0]["tokens"] == 175
```

- [ ] **Step 6: Run it, confirm it fails (module `tasks` can't see `project_root` yet since Step 2's conftest must be picked up — this should actually PASS if Step 2 is correct; if it fails with `fixture 'project_root' not found`, conftest.py isn't in the right place)**

Run: `PYTHONPATH=plugins/monitor/skills/monitor/scripts pytest tests/unit/test_tasks.py -v`
Expected: 5 passed. (These tests exercise existing, already-correct code — Task 3 is about building the harness, not fixing bugs, so "RED" here just means "harness broken," not "feature missing"; a clean pass on the first real run confirms the fixture works.)

- [ ] **Step 7: Write `tests/unit/test_render_tasks.py`**

```python
import render_tasks


SAMPLE_MTR = """2026-07-27 10:00:00,000 INFO [task-close] (aaaa1111) done -- success
task_id: aaaa1111
branch:  main
================================================================================
2026-07-27 09:00:00,000 INFO [task-start] (aaaa1111) started: Demo -- open
task_id: aaaa1111
title:   Demo
branch:  main
================================================================================
"""


def test_parse_tasks_extracts_fields():
    entries = render_tasks.parse_tasks(SAMPLE_MTR)
    assert len(entries) == 2
    assert entries[0]["event"] == "task-close"
    assert entries[1]["title"] == "Demo"


def test_group_tasks_created_at_is_task_start_time():
    entries = render_tasks.parse_tasks(SAMPLE_MTR)
    groups = render_tasks.group_tasks(entries)
    assert groups[0]["created_at"] == "2026-07-27 09:00:00,000"
    assert groups[0]["status"] == "success"  # most recent event's status


def test_block_task_id_ignores_mentions_in_details():
    block = ('2026-07-27 10:00:00,000 INFO [task-close] (bbbb2222) done -- success\n'
             'task_id: bbbb2222\n'
             'details: follow-on from task_id: aaaa1111')
    assert render_tasks.block_task_id(block) == "bbbb2222"
```

- [ ] **Step 8: Run it, confirm passing**

Run: `PYTHONPATH=plugins/monitor/skills/monitor/scripts pytest tests/unit/test_render_tasks.py -v`
Expected: 3 passed.

- [ ] **Step 9: Write `tests/unit/test_pending.py`**

```python
import pending
import tasks


def test_open_tasks_lists_nonterminal_only(project_root):
    tasks.start_task(project_root, title="Still open")
    closed_id = tasks.start_task(project_root, title="Will close")
    tasks.close_task(project_root, task_id=closed_id, status="success", summary="done")
    open_list = pending.open_tasks(project_root)
    assert len(open_list) == 1
    assert open_list[0]["title"] == "Still open"


def test_check_text_mentions_open_task(project_root):
    tasks.start_task(project_root, title="Needs attention")
    text = pending.check_text(project_root)
    assert "Needs attention" in text
    assert "open task" in text


def test_check_text_empty_when_nothing_pending(project_root):
    assert pending.check_text(project_root) == ""


def test_clear_log_drains_oldest_reachable_entry(project_root):
    data = pending.load_pending(project_root)
    data["pending_logs"] = [{"sha": "deadbeef", "message": "x", "committed_at": "now"}]
    pending.save_pending(project_root, data)
    pending.clear_log(project_root, "deadbeef")
    assert pending.load_pending(project_root)["pending_logs"] == []
```

- [ ] **Step 10: Run it, confirm passing**

Run: `PYTHONPATH=plugins/monitor/skills/monitor/scripts pytest tests/unit/test_pending.py -v`
Expected: 4 passed.

- [ ] **Step 11: Write `tests/unit/test_clean.py`**

```python
import time

import clean
import tasks


def test_clean_tasks_removes_by_creation_order(project_root):
    a_id = tasks.start_task(project_root, title="Task A (really oldest)")
    time.sleep(1.1)
    tasks.start_task(project_root, title="Task B (really newest)")
    time.sleep(1.1)
    tasks.update_task(project_root, task_id=a_id, status="in_progress", summary="still going")
    clean.clean_tasks(project_root, 1, dry=False)
    text = (project_root / "monitor" / "tasks" / "tasks.mtr").read_text()
    assert f"task_id: {a_id}" not in text
    assert "Task B" in text


def test_clean_tasks_never_deletes_by_substring_mention(project_root):
    victim_id = tasks.start_task(project_root, title="Victim")
    survivor_id = tasks.start_task(project_root, title="Survivor")
    tasks.update_task(project_root, task_id=survivor_id, status="in_progress",
                      summary="ref", details=f"follow-on from task_id: {victim_id}")
    time.sleep(1.1)
    tasks.close_task(project_root, task_id=survivor_id, status="success", summary="done")
    clean.clean_tasks(project_root, 1, dry=False)  # should remove only the oldest (victim)
    text = (project_root / "monitor" / "tasks" / "tasks.mtr").read_text()
    assert f"task_id: {victim_id}" not in text
    assert f"task_id: {survivor_id}" in text
```

- [ ] **Step 12: Run it, confirm passing**

Run: `PYTHONPATH=plugins/monitor/skills/monitor/scripts pytest tests/unit/test_clean.py -v`
Expected: 2 passed.

- [ ] **Step 13: Write `tests/integration/test_task_lifecycle_flow.py`**

```python
"""Integration: the full start -> update -> close flow, checked against the
rendered HTML, not just the .mtr text — this is what a real agent session
actually looks at."""

import tasks
import render_tasks


def test_full_lifecycle_renders_correct_dashboard_kpi(project_root):
    task_id = tasks.start_task(project_root, title="Ship the thing")
    assert render_tasks.count_open(project_root) == 1
    tasks.update_task(project_root, task_id=task_id, status="in_progress", summary="working")
    assert render_tasks.count_open(project_root) == 1
    tasks.close_task(project_root, task_id=task_id, status="success", summary="shipped")
    assert render_tasks.count_open(project_root) == 0
    html = (project_root / "monitor" / "tasks" / "index.html").read_text()
    assert task_id in html
    assert "SUCCESS" in html
```

- [ ] **Step 14: Run it, confirm passing**

Run: `PYTHONPATH=plugins/monitor/skills/monitor/scripts pytest tests/integration/test_task_lifecycle_flow.py -v`
Expected: 1 passed.

- [ ] **Step 15: Write `tests/integration/test_pending_hook_flow.py`**

```python
"""Integration: the real hook entrypoints (hook_post_tool_use /
hook_user_prompt_submit), driven the same way Claude Code's hook runner
actually calls them — via stdin JSON, not the plain track()/check_text()
helpers directly."""

import io
import json
import subprocess
import sys

import pending


def test_unlogged_commit_then_clears_on_log(project_root, monkeypatch):
    (project_root / "f.txt").write_text("x")
    subprocess.run(["git", "add", "f.txt"], cwd=project_root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "add f.txt"], cwd=project_root, check=True)
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=project_root,
                         capture_output=True, text=True, check=True).stdout.strip()

    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "git commit -m x"}})
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
    pending.hook_post_tool_use(project_root)
    data = pending.load_pending(project_root)
    assert any(e["sha"] == sha for e in data["pending_logs"])

    import logger
    logger.log_operation(project_root, operation="add-file", tool="Bash",
                         summary="added f.txt", status="success", last_commit_hash=sha)
    data = pending.load_pending(project_root)
    assert data["pending_logs"] == []
```

- [ ] **Step 16: Run it, confirm passing**

Run: `PYTHONPATH=plugins/monitor/skills/monitor/scripts pytest tests/integration/test_pending_hook_flow.py -v`
Expected: 1 passed.

- [ ] **Step 17: Run the whole suite together**

Run: `PYTHONPATH=plugins/monitor/skills/monitor/scripts pytest tests/ -v`
Expected: all tests from Steps 3-16 pass (19 total), no errors, no warnings about missing fixtures.

- [ ] **Step 18: Commit**

```bash
cd /Users/ojaswi/Projects/monitor-tools
git add requirements-dev.txt tests/
git commit -m "test: add pytest suite for the monitor engine (unit + integration)"
```

---

### Task 4: `test-unit` and `test-integration` skills

**Files:**
- Create: `.claude/skills/test-unit/SKILL.md`
- Create: `.claude/skills/test-integration/SKILL.md`

**Interfaces:**
- Consumes: `tests/unit/`, `tests/integration/`, `requirements-dev.txt` (Task 3).

- [ ] **Step 1: Write `.claude/skills/test-unit/SKILL.md`**

```markdown
---
name: test-unit
description: Runs the monitor engine's unit test suite (tests/unit/) — fast, isolated pytest tests with no subprocess/install-flow dependencies. Use when asked to run unit tests, check the engine's core logic, or verify a change to a single script didn't break its contracts.
---

# test-unit

Runs `tests/unit/` — one function/behavior at a time, each against a fresh
`tmp_path` scratch project (via `tests/conftest.py`'s `project_root`
fixture), never this repo's own real `monitor/` directory.

## Flow

1. Ensure pytest is available: `pip install -r requirements-dev.txt -q`
   (skip if already importable — check with `python3 -c "import pytest"`
   first, only install on failure).
2. Run: `PYTHONPATH=plugins/monitor/skills/monitor/scripts pytest tests/unit/ -v`
3. Relay the pass/fail summary and, on any failure, the failing test names
   and assertion output verbatim — don't paraphrase a traceback.

## Notes

- This skill is not part of the `monitor` plugin; it is never copied into
  `plugins/monitor/`.
- Distinct from `test-integration` (multi-script flows) and `test-e2e`
  (live dogfood drill against real cloned repos, manual/on-demand only).
```

- [ ] **Step 2: Write `.claude/skills/test-integration/SKILL.md`**

```markdown
---
name: test-integration
description: Runs the monitor engine's integration test suite (tests/integration/) — multi-script flows (task lifecycle, pending-hook dispatch) against a fresh scratch project. Use when asked to run integration tests or verify a cross-script flow still works end to end.
---

# test-integration

Runs `tests/integration/` — exercises multiple engine scripts together
(e.g. the full task start→update→close flow checked against rendered
HTML, or a real `git commit` driving the actual hook entrypoints via
stdin JSON) against a fresh `tmp_path` scratch project.

## Flow

1. Ensure pytest is available: `pip install -r requirements-dev.txt -q`
   (skip if already importable — check with `python3 -c "import pytest"`
   first, only install on failure).
2. Run: `PYTHONPATH=plugins/monitor/skills/monitor/scripts pytest tests/integration/ -v`
3. Relay the pass/fail summary and, on any failure, the failing test names
   and assertion output verbatim — don't paraphrase a traceback.

## Notes

- This skill is not part of the `monitor` plugin; it is never copied into
  `plugins/monitor/`.
- Distinct from `test-unit` (single-function checks) and `test-e2e` (live
  dogfood drill against real cloned repos, manual/on-demand only).
```

- [ ] **Step 3: Verify both skills' documented commands actually work**

Run: `pip install -r requirements-dev.txt -q && PYTHONPATH=plugins/monitor/skills/monitor/scripts pytest tests/unit/ -v && PYTHONPATH=plugins/monitor/skills/monitor/scripts pytest tests/integration/ -v`
Expected: both suites pass (same result as Task 3 Step 17, split into two runs) — confirms the two skills' documented commands are exactly correct, not approximate.

- [ ] **Step 4: Commit**

```bash
cd /Users/ojaswi/Projects/monitor-tools
git add .claude/skills/test-unit/SKILL.md .claude/skills/test-integration/SKILL.md
git commit -m "feat: add test-unit and test-integration skills"
```

---

### Task 5: `search.py` covers reports and tasks

**Files:**
- Modify: `plugins/monitor/skills/monitor/scripts/search.py`

**Interfaces:**
- Consumes: `render_report.scan_reports(root) -> list[dict]`, `render_report._plain(s) -> str` (existing tag-stripping helper), `render_tasks.parse_tasks(text) -> list[dict]`.
- Produces: `search.search_reports(root, query, *, limit) -> list[dict]`, `search.search_tasks(root, query, *, limit) -> list[dict]` — each returned dict has enough fields for `format_report_match()`/`format_task_match()` (defined in this task) to render it.

- [ ] **Step 1: Manual verification script (search.py has no fixture-based tests yet in this task — Task 3's suite predates this change; add a Step 10 pytest file at the end of this task instead of a manual script, since `project_root` already exists)**

Skip a standalone manual script here — go straight to a pytest test file since Task 3's fixture is available. Write `tests/unit/test_search.py` now (Step 2 below is the actual first step); this task's "RED" step is running that new test file before the implementation exists.

- [ ] **Step 2: Write `tests/unit/test_search.py`**

```python
import search
import tasks


def test_search_tasks_matches_details(project_root):
    task_id = tasks.start_task(project_root, title="Fix the thing",
                               details="DECISION: use approach X")
    matches = search.search_tasks(project_root, "approach X")
    assert len(matches) == 1
    assert matches[0]["task_id"] == task_id


def test_search_reports_matches_body_text(project_root):
    reports_dir = project_root / "monitor" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "2026-07-27-demo.html").write_text(
        "<html><body><h1>Demo Report</h1><p>Fixed the flibbertigibbet bug.</p></body></html>")
    matches = search.search_reports(project_root, "flibbertigibbet")
    assert len(matches) == 1
    assert matches[0]["title"] == "Demo Report"


def test_search_scope_all_covers_every_source(project_root):
    tasks.start_task(project_root, title="uniqueword task")
    import logger
    logger.log_operation(project_root, operation="op", tool="Bash",
                         summary="uniqueword log", status="success")
    matches = search.search(project_root, "uniqueword", scope="all")
    assert set(matches.keys()) == {"logs", "reports", "tasks"}
    assert len(matches["logs"]) == 1
    assert len(matches["tasks"]) == 1
    assert len(matches["reports"]) == 0
```

- [ ] **Step 3: Run it, confirm it fails**

Run: `PYTHONPATH=plugins/monitor/skills/monitor/scripts pytest tests/unit/test_search.py -v`
Expected: `AttributeError: module 'search' has no attribute 'search_tasks'` (and similar for `search_reports`/the new `search()` scope signature) — today's `search()` only covers logs and takes no `scope` argument.

- [ ] **Step 4: Implement the scope extension in `search.py`**

Replace the module's imports and add the two new search functions (insert after the existing `search()` function, before `format_match()`):
```python
import logger
import monitor_lib as mlib
import render_logs
import render_report
import render_tasks
```
(add `import render_report` and `import render_tasks` to the existing `import logger` / `import monitor_lib as mlib` / `import render_logs` block)

```python
def search_reports(root: Path, query: str, *, limit: int = 20) -> list[dict]:
    if limit <= 0:
        return []
    q = query.lower()
    matches = []
    for item in render_report.scan_reports(root):
        path = mlib.monitor_dir(root) / "reports" / item["file"]
        text = render_report._plain(path.read_text(encoding="utf-8"))
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
```

Replace `search()`'s signature and body to add the `scope` parameter — the existing single-scope behavior becomes the `logs`-only path:
```python
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
```
(This renames the old `search()` body to `_search_logs()` verbatim and makes `search()` a thin dispatcher — every existing call site that used positional/keyword args matching the old signature still works since `scope` defaults to `"logs"`, the prior sole behavior.)

Update `main()` to add `--scope` and print sectioned output for `all`:
```python
    ap.add_argument("--scope", default="all", choices=("logs", "reports", "tasks", "all"))
```
(add this line to the existing arg block, near `--query`)

Replace the tail of `main()` (from `matches = search(...)` onward):
```python
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
```

- [ ] **Step 5: Run the Step 2 test file, confirm it passes**

Run: `PYTHONPATH=plugins/monitor/skills/monitor/scripts pytest tests/unit/test_search.py -v`
Expected: 3 passed.

- [ ] **Step 6: Run the full suite to confirm no regressions**

Run: `PYTHONPATH=plugins/monitor/skills/monitor/scripts pytest tests/ -v`
Expected: all previously-passing tests (Task 3) still pass, plus the 3 new ones.

- [ ] **Step 7: Update `commands/search.md` and `SKILL.md` for the new `--scope` flag**

In `plugins/monitor/commands/search.md`, replace the engine invocation block:
```
python3 monitor/scripts/search.py --project-root . --query "<text>" \
    [--scope logs|reports|tasks|all] \
    [--branch <name>] [--status success|partial|failure] [--level LEVEL] [--limit N]
```
Add one sentence after the existing "Output is plain text..." line: "`--scope` defaults to `all` (every source); narrow to `logs`/`reports`/`tasks` to search just one. `--branch`/`--status`/`--level` only apply when the effective scope includes logs."

In `plugins/monitor/skills/monitor/SKILL.md`, find the line documenting `logger.py`'s CLI shape (the `--task-id`/`--last-commit-hash` line in the Logging section) — leave that alone; instead add one line to the "Common mistakes" table:
```markdown
| Assuming `/monitor:search` only covers logs | It covers logs, reports, and tasks by default (`--scope all`); narrow with `--scope logs|reports|tasks` if you only want one source. |
```

- [ ] **Step 8: Commit**

```bash
cd /Users/ojaswi/Projects/monitor-tools
git add plugins/monitor/skills/monitor/scripts/search.py plugins/monitor/commands/search.md plugins/monitor/skills/monitor/SKILL.md tests/unit/test_search.py
git commit -m "feat: search.py covers reports and tasks via --scope, defaults to all sources"
```

---

### Task 6: Dashboard grep search box

**Files:**
- Modify: `plugins/monitor/skills/monitor/scripts/render_report.py`

**Interfaces:**
- Consumes: `render_logs.parse_log()`, `render_report.scan_reports()`, `render_tasks.parse_tasks()`/`group_tasks()` (all existing).

- [ ] **Step 1: Write a pytest check for the embedded search data (no visual/browser test — verifying the generated HTML is well-formed and contains real data, per the spec's stated verification method)**

Write `tests/integration/test_search_flow.py`:
```python
"""Integration: the Dashboard's embedded search index actually contains
real entries from all three sources after a full log+report+task round."""

import json
import re

import tasks


def test_dashboard_embeds_searchable_index(project_root):
    import logger
    logger.log_operation(project_root, operation="fix-bug", tool="Edit",
                         summary="Fixed the login bug", status="success")
    tasks.start_task(project_root, title="Ship the login fix")

    import render_report
    profile = {"project": {"name": "demo"}, "kpis": [], "notes": {}}
    render_report.render_dashboard(profile, 0, project_root, "main")

    html = (project_root / "monitor" / "index.html").read_text()
    m = re.search(r'const MONITOR_SEARCH_INDEX = (\[.*?\]);', html, re.S)
    assert m, "expected an embedded MONITOR_SEARCH_INDEX array in index.html"
    index = json.loads(m.group(1))
    titles = [item["title"] for item in index]
    assert any("login bug" in t for t in titles)
    assert any("login fix" in t for t in titles)
    assert '<input' in html and 'id="monitor-search"' in html
```

- [ ] **Step 2: Run it, confirm it fails**

Run: `PYTHONPATH=plugins/monitor/skills/monitor/scripts pytest tests/integration/test_search_flow.py -v`
Expected: `AssertionError: expected an embedded MONITOR_SEARCH_INDEX array in index.html` — today's Dashboard has no search box.

- [ ] **Step 3: Add the search index + box to `render_dashboard()`**

Add a helper function before `render_dashboard()` in `render_report.py`:
```python
def _build_search_index(root: Path) -> list[dict]:
    """Small, title/summary-only index for the Dashboard's client-side grep
    box — deliberately excludes full --details/body text to keep the
    embedded payload small; this is a quick-find aid, not a replacement
    for /monitor:search's full-text matching."""
    mdir = mlib.monitor_dir(root)
    index: list[dict] = []
    log_path = mdir / "logs" / "operations.mtr"
    if log_path.exists():
        for e in render_logs.parse_log(log_path.read_text(encoding="utf-8")):
            if e.get("fragment") is not None:
                continue
            index.append({"kind": "log", "title": e["summary"],
                          "href": "logs/index.html"})
    for item in scan_reports(root):
        index.append({"kind": "report", "title": item["title"],
                      "href": f"reports/{item['file']}"})
    tasks_path = mdir / "tasks" / "tasks.mtr"
    if tasks_path.exists():
        for g in render_tasks.group_tasks(render_tasks.parse_tasks(
                tasks_path.read_text(encoding="utf-8"))):
            index.append({"kind": "task", "title": g["title"] or g["task_id"],
                          "href": "tasks/index.html"})
    return index
```

In `render_dashboard()`, add the index build near the top (after `n_open_tasks = render_tasks.count_open(root)`):
```python
    search_index = _build_search_index(root)
```

Add the search box markup right after the `<div class="kpis">...</div>` block's closing `"""` in the `header` f-string — change:
```python
  </div>"""
    body = """  <div class="card-grid">
```
to:
```python
  </div>

  <div class="dsearch">
    <input type="text" id="monitor-search" placeholder="Search titles across logs, reports, tasks..." autocomplete="off">
    <ul id="monitor-search-results"></ul>
  </div>"""
    body = """  <div class="card-grid">
```

Add the script tag as its own variable, appended after `body` in the `mlib.page(...)` call. Change:
```python
    out = mlib.page(f"{brand} · Monitor", brand, "info", "Monitor", header, body,
                    footer, branch=branch)
    (mdir / "index.html").write_text(out, encoding="utf-8")
```
to:
```python
    import json as _json
    script = f"""<script>
const MONITOR_SEARCH_INDEX = {_json.dumps(search_index)};
(function() {{
  const input = document.getElementById('monitor-search');
  const results = document.getElementById('monitor-search-results');
  input.addEventListener('input', function() {{
    const q = input.value.trim().toLowerCase();
    results.innerHTML = '';
    if (!q) return;
    MONITOR_SEARCH_INDEX
      .filter(item => item.title.toLowerCase().includes(q))
      .slice(0, 20)
      .forEach(item => {{
        const li = document.createElement('li');
        const a = document.createElement('a');
        a.href = item.href;
        a.textContent = '[' + item.kind + '] ' + item.title;
        li.appendChild(a);
        results.appendChild(li);
      }});
  }});
}})();
</script>"""
    out = mlib.page(f"{brand} · Monitor", brand, "info", "Monitor", header, body,
                    footer, branch=branch)
    out = out.replace('</body>', script + '\n</body>')
    (mdir / "index.html").write_text(out, encoding="utf-8")
```

Add two small CSS rules to `monitor_lib.PALETTE_CSS` (the single shared stylesheet — this is the one narrow addition of new selectors, styled consistently with the existing chip/list conventions already in the file). Insert right after the `.card-grid`/`.navcard` rules:
```css
  .dsearch { margin-top: 20px; }
  .dsearch input { width: 100%; border: 1px solid var(--border); background: var(--surface); color: var(--text); padding: 10px 14px; font-size: 0.92rem; font-family: inherit; }
  .dsearch input:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
  .dsearch ul { list-style: none; margin-top: 8px; }
  .dsearch li { border-bottom: 1px solid var(--hairline); padding: 6px 2px; font-size: 0.88rem; }
  .dsearch li:last-child { border-bottom: none; }
```

- [ ] **Step 4: Run the Step 1 test, confirm it passes**

Run: `PYTHONPATH=plugins/monitor/skills/monitor/scripts pytest tests/integration/test_search_flow.py -v`
Expected: 1 passed.

- [ ] **Step 5: Run the full suite, confirm no regressions**

Run: `PYTHONPATH=plugins/monitor/skills/monitor/scripts pytest tests/ -v`
Expected: all prior tests still pass, plus this new one.

- [ ] **Step 6: Commit**

```bash
cd /Users/ojaswi/Projects/monitor-tools
git add plugins/monitor/skills/monitor/scripts/render_report.py tests/integration/test_search_flow.py
git commit -m "feat: add a client-side grep search box to the Dashboard (the one page-level JS exception)"
```

---

### Task 7: Report `date_created` / `last_modified` placeholders

**Files:**
- Modify: `plugins/monitor/skills/monitor/scripts/render_report.py`

**Interfaces:**
- Produces: `lock_report_style()` also stamps `{{ last_modified }}` with the current timestamp when it corrects a report's style block.

- [ ] **Step 1: Write the failing test**

Add to (new file) `tests/unit/test_render_report_timestamps.py`:
```python
import render_report


def test_template_has_date_created_and_last_modified_placeholders(project_root):
    profile = {"project": {"name": "demo"}, "kpis": [], "notes": {}}
    render_report.render_template(profile, project_root)
    template = (project_root / "monitor" / "reports" / "template.html").read_text()
    assert "{{ date_created }}" in template
    assert "{{ last_modified }}" in template


def test_lock_report_stamps_last_modified(project_root):
    reports_dir = project_root / "monitor" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / "2026-07-27-demo.html"
    report_path.write_text(
        f"<html><head><style>{render_report.mlib.PALETTE_CSS}</style></head>"
        "<body><p>{{ last_modified }}</p></body></html>")
    render_report.lock_report_style(project_root, "2026-07-27-demo.html")
    text = report_path.read_text()
    assert "{{ last_modified }}" not in text  # got replaced with a real stamp
```

- [ ] **Step 2: Run it, confirm it fails**

Run: `PYTHONPATH=plugins/monitor/skills/monitor/scripts pytest tests/unit/test_render_report_timestamps.py -v`
Expected: first test fails (`{{ date_created }}` not in template — today's template only has `{{ date }}`); second fails too (`lock_report_style` doesn't touch `{{ last_modified }}` yet).

- [ ] **Step 3: Add the two placeholders to `render_template()`**

In `render_template()`'s `header` f-string, add two chips after the existing `Generated` chip:
```python
      <span class="chip"><b>Generated</b><span class="mono">{{{{ date }}}}</span></span>
      <span class="chip"><b>Created</b><span class="mono">{{{{ date_created }}}}</span></span>
      <span class="chip"><b>Last modified</b><span class="mono">{{{{ last_modified }}}}</span></span>
      <span class="chip"><b>Branch</b><span class="mono">{{{{ branch }}}}</span></span>
```
(inserted between the `Generated` and `Branch` chips — the existing `Commit`/`Status` chips stay where they are, unchanged.)

- [ ] **Step 4: Make `lock_report_style()` stamp `last_modified`**

Replace `lock_report_style()`:
```python
def lock_report_style(root: Path, report_rel_path: str) -> bool:
    """Force a freshly authored report back onto the canonical palette/theme,
    and stamp {{ last_modified }} with the lock moment — the point a report
    is considered finalized. Content-tone requests (audience, reading level,
    language, humor) must only ever change the prose inside a report's
    sections — never its <style> block, since that block IS the design/theme
    lock (mlib.PALETTE_CSS is the single source of truth, shared by every
    generated page). This is a one-time correction run right after a report
    is authored, not a general "resync all reports" — running it on old
    reports would violate the immutable-snapshot rule if the canonical
    palette changes later. Also strips any <script> tag an authoring pass
    may have added (reports are self-contained HTML/CSS only, no <script>,
    per SKILL.md). Returns True if the file needed correcting.
    """
    path = mlib.monitor_dir(root) / "reports" / report_rel_path
    text = path.read_text(encoding="utf-8")
    fixed = STYLE_RE.sub(lambda _m: f"<style>{mlib.PALETTE_CSS}</style>", text, count=1)
    fixed = SCRIPT_RE.sub("", fixed)
    fixed = fixed.replace("{{ last_modified }}", datetime.now().strftime("%Y-%m-%d %H:%M"))
    if fixed != text:
        path.write_text(fixed, encoding="utf-8")
        return True
    return False
```
(Only the `fixed = fixed.replace(...)` line and the docstring's first sentence are new — everything else is byte-identical to the current function. `datetime` is already imported at the top of the file.)

- [ ] **Step 5: Update `commands/report.md` to tell the authoring agent to fill `date_created`**

In `plugins/monitor/commands/report.md`, in the numbered authoring step (the one that says "Fill every `{{ branch }}` placeholder..."), add one sentence: "Fill `{{ date_created }}` with the date the underlying work began (your own judgment, distinct from `{{ date }}`/`{{ last_modified }}`, both of which are stamped automatically). Leave `{{ last_modified }}` alone — `render_report.py --lock-report` fills it in automatically at the end of authoring."

- [ ] **Step 6: Run the Step 1 tests, confirm they pass**

Run: `PYTHONPATH=plugins/monitor/skills/monitor/scripts pytest tests/unit/test_render_report_timestamps.py -v`
Expected: 2 passed.

- [ ] **Step 7: Run the full suite, confirm no regressions**

Run: `PYTHONPATH=plugins/monitor/skills/monitor/scripts pytest tests/ -v`
Expected: all prior tests still pass, plus these 2.

- [ ] **Step 8: Commit**

```bash
cd /Users/ojaswi/Projects/monitor-tools
git add plugins/monitor/skills/monitor/scripts/render_report.py plugins/monitor/commands/report.md tests/unit/test_render_report_timestamps.py
git commit -m "feat: add date_created/last_modified report timestamp placeholders"
```

---

### Task 8: `test-thought-leaks` skill + script

**Files:**
- Create: `scripts/check_thought_leaks.py`
- Create: `.claude/skills/test-thought-leaks/SKILL.md`

**Interfaces:**
- Produces: `scripts/check_thought_leaks.py` is a standalone CLI, exit 0 (clean) / 1 (hits found) — same contract pytest itself uses, but this is not a pytest test (it's meant to scan prose, and false positives are expected and require human judgment per the spec, so it must not silently fail a CI-style gate).

- [ ] **Step 1: Write `scripts/check_thought_leaks.py`**

```python
#!/usr/bin/env python3
"""Grep this repo's shipped documentation for development-history/reasoning-
leakage language, per this repo's own CLAUDE.md rule: no version narration,
no "this was previously X", no meta-commentary about prior approaches in
any user-facing doc. Flags candidates for human/agent review — a hit is
not automatically a real leak (e.g. "previously" can appear in an
unrelated, legitimate sentence), so this never auto-fails a commit; it
prints matches for judgment.

Usage:  python3 scripts/check_thought_leaks.py
Exit code: 1 if anything matched (for scripting), 0 if clean.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

TARGET_GLOBS = [
    "plugins/monitor/skills/monitor/SKILL.md",
    "plugins/monitor/commands/*.md",
    "README.md",
    ".claude/skills/test-e2e/SKILL.md",
    ".claude/skills/test-unit/SKILL.md",
    ".claude/skills/test-integration/SKILL.md",
    "CLAUDE.md",
    "AGENTS.md",
]

PATTERNS = [
    re.compile(p, re.I) for p in [
        r"\bversion\s+\d+\b",
        r"\bused to\b",
        r"\bpreviously\b",
        r"\bremoved (in|because)\b",
        r"\bearlier version\b",
        r"\bthis was later\b",
        r"\bdeprecated\b",
        r"\bearlier (implementation|approach)\b",
    ]
]


def find_hits() -> list[tuple[Path, int, str]]:
    hits: list[tuple[Path, int, str]] = []
    seen: set[Path] = set()
    for pattern in TARGET_GLOBS:
        for path in sorted(REPO_ROOT.glob(pattern)):
            if path in seen or not path.is_file():
                continue
            seen.add(path)
            for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                for regex in PATTERNS:
                    m = regex.search(line)
                    if m:
                        hits.append((path.relative_to(REPO_ROOT), i, m.group(0)))
    return hits


def main() -> int:
    hits = find_hits()
    if not hits:
        print("clean: no development-history/reasoning-leakage phrases found")
        return 0
    print(f"{len(hits)} candidate(s) found — review each for a real leak vs. a false positive:\n")
    for path, line_no, text in hits:
        print(f"{path}:{line_no}: {text!r}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run it against the current repo to verify it works and see the baseline**

Run: `python3 scripts/check_thought_leaks.py`
Expected: exits 0 with `clean: ...` (this session's own docs were already hand-audited for this rule earlier), OR exits 1 with a short list — if it finds real hits, fix them now as part of this task (they're pre-existing gaps this new tool is catching, in scope to fix here since finding-but-not-fixing a real leak defeats the point of adding this check).

- [ ] **Step 3: Write `.claude/skills/test-thought-leaks/SKILL.md`**

```markdown
---
name: test-thought-leaks
description: Scans monitor's shipped documentation for development-history, version-changelog, or reasoning-leakage language, per this repo's CLAUDE.md rule. Use when asked to check for thought leaks, dev-history leakage, or before finishing a branch that touched SKILL.md/README.md/commands/*.md.
---

# test-thought-leaks

Runs `scripts/check_thought_leaks.py`, which greps a fixed list of shipped
doc files for phrases like "used to", "previously", "removed because",
"version N", "deprecated" — candidates for the kind of narration
`CLAUDE.md` explicitly bans from user-facing documentation.

## Flow

1. Run: `python3 scripts/check_thought_leaks.py`
2. Exit 0 means clean — relay that and stop.
3. Exit 1 means candidates were found — **read each one yourself**, don't
   treat a hit as an automatic failure. The script flags phrases, not
   confirmed leaks: "previously" inside a legitimate, unrelated sentence
   is a false positive. For each real leak, fix the wording to state
   current behavior only, then re-run the script to confirm it's now
   clean. For each false positive, note it and move on — nothing to fix.
4. Relay a final summary: how many hits were real leaks (fixed), how many
   were false positives (left as-is), and confirm the script now exits 0.

## Notes

- This skill is not part of the `monitor` plugin; it is never copied into
  `plugins/monitor/`.
- The script's target file list is fixed in code
  (`scripts/check_thought_leaks.py`'s `TARGET_GLOBS`) — if a new shipped
  doc file is added to the repo, add it there too.
```

- [ ] **Step 4: Commit**

```bash
cd /Users/ojaswi/Projects/monitor-tools
git add scripts/check_thought_leaks.py .claude/skills/test-thought-leaks/SKILL.md
git commit -m "feat: add test-thought-leaks skill to automate dev-history-leakage checks"
```

---

### Task 9: `test-automated` skill

**Files:**
- Create: `.claude/skills/test-automated/SKILL.md`

**Interfaces:**
- Consumes: `test-unit` (Task 4), `test-integration` (Task 4), `test-thought-leaks` (Task 8) — this skill's instructions reference their exact commands directly (skills can't programmatically invoke each other; this skill's SKILL.md tells the agent to run all three commands in sequence).

- [ ] **Step 1: Write `.claude/skills/test-automated/SKILL.md`**

```markdown
---
name: test-automated
description: Runs the full automated check set for monitor — unit tests, integration tests, and the thought-leak scan — in one pass. Use when asked to run all automated tests, do a full check before finishing a branch, or verify nothing regressed after an engine change. Does not run test-e2e (the live dogfood drill stays manual/on-demand).
---

# test-automated

Runs, in order, reporting each result separately (never merged into one
opaque pass/fail):

1. **Unit tests** — `pip install -r requirements-dev.txt -q` (skip if
   pytest already importable), then
   `PYTHONPATH=plugins/monitor/skills/monitor/scripts pytest tests/unit/ -v`.
2. **Integration tests** —
   `PYTHONPATH=plugins/monitor/skills/monitor/scripts pytest tests/integration/ -v`.
3. **Thought-leak scan** — `python3 scripts/check_thought_leaks.py`; per
   `test-thought-leaks`'s own rule, a nonzero exit means candidates to
   review by hand, not an automatic failure — read each hit and judge it
   yourself before reporting this step's outcome.

## Flow

Run all three in sequence (stop and report immediately if either pytest
run fails — don't run the next step on top of a known-broken suite; the
thought-leak scan has no such gate since its own hits require judgment,
not a hard stop). Relay one summary at the end: unit (pass/fail count),
integration (pass/fail count), thought-leaks (clean / N reviewed, M fixed).

## Notes

- This skill is not part of the `monitor` plugin; it is never copied into
  `plugins/monitor/`.
- Does **not** invoke `test-e2e` — that stays manual/on-demand, run
  separately whenever a live dogfood drill against real cloned repos is
  wanted.
```

- [ ] **Step 2: Verify the full sequence works end to end**

Run:
```bash
pip install -r requirements-dev.txt -q
PYTHONPATH=plugins/monitor/skills/monitor/scripts pytest tests/unit/ -v
PYTHONPATH=plugins/monitor/skills/monitor/scripts pytest tests/integration/ -v
python3 scripts/check_thought_leaks.py
```
Expected: both pytest runs pass in full (every test from Tasks 3, 5, 6, 7 — 26 tests total: 4+5+3+4+2 unit from Task 3's Steps 3/5/7/9/11, +3 from Task 5, +2 from Task 7 = 21 unit; 1+1+1 integration from Task 3's Steps 13/15 and Task 6's Step 1 = 3 integration; recount not required — this step's pass/fail is what matters, not an exact number), and the leak scan exits 0 or with only-already-reviewed hits.

- [ ] **Step 3: Commit**

```bash
cd /Users/ojaswi/Projects/monitor-tools
git add .claude/skills/test-automated/SKILL.md
git commit -m "feat: add test-automated skill running unit + integration + thought-leaks together"
```

---

## Self-Review Notes

**Spec coverage:** all 7 spec items map onto tasks — item 1 → Task 1, item 2 → Task 2, item 3 → Tasks 3-4, item 4 → Tasks 5-6, item 5 → Task 7, item 6 → Task 8, item 7 → Task 9.

**Placeholder scan:** every step has real code or a real, runnable verification command — no "add appropriate tests" hand-waving.

**Type/signature consistency:** `render_tasks.group_tasks()`'s new `created_at` key (Task 2) is consumed correctly by `clean.py` (Task 2) and referenced by name only, not re-derived, in Task 3's `test_render_tasks.py`. `search.py`'s `search()` scope dispatch (Task 5) preserves the exact old positional/keyword signature as the `scope="logs"` default, so Task 3's fixtures and any future caller relying on the old shape keep working — verified explicitly in Task 5 Step 6 (full-suite re-run). `pending.open_tasks()` (Task 1) and `render_dashboard()`'s `_build_search_index()` (Task 6) both independently call `render_tasks.group_tasks()`/`parse_tasks()` with the same signatures used everywhere else in the codebase — no invented alternate call shape.

**Dependency order:** Task 4 depends on Task 3 (tests must exist for the skills to document/verify real commands); Task 9 depends on Tasks 4 and 8 (references their exact commands). Tasks 1, 2, 5, 6, 7 are independent of each other but all depend on Task 3 existing before their own pytest files can run (each adds new files under `tests/`, using Task 3's `conftest.py` fixture) — sequencing Task 3 third (after two small non-test-suite fixes) rather than first was a deliberate call: Tasks 1-2 are complete, testable-by-manual-script features on their own, and Task 3 is large enough that landing two real fixes before it keeps early review cycles small. If executed by subagent-driven-development in strict task order, this dependency holds correctly since Tasks 1-2's manual verification scripts don't need `tests/` to exist at all.
