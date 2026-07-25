# Monitor Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `search.py` engine script + `/monitor:search` command so an agent can grep the operations log for past decisions instead of paging through static HTML by hand, and thread commit hashes through log entries and reports for traceability.

**Architecture:** Every log entry automatically records the git `HEAD` short sha at the moment it's logged — a new `last_commit_hash` field, auto-captured by `logger.py` exactly like `branch` already is (no agent action required, works even for entries the user triggers by hand). `search.py` is a new stdlib-only engine script that reuses `render_logs.parse_log()` (already the canonical entry parser) to filter `monitor/logs/operations.mtr` by a case-insensitive substring query plus optional `--branch`/`--status`/`--level` filters, printing plain-text matches — no new HTML page, since a search result is dynamic and every other monitor page is static/pre-built. Reports fill the existing (currently-unused) `{{ commit }}` template placeholder with a `first..last` short-sha range covering the report.

**Tech Stack:** Python 3 stdlib only (matches the rest of the engine — no new dependencies).

## Global Constraints

- Engine scripts are stdlib-only Python 3, no third-party dependencies (project-wide rule, `CLAUDE.md`).
- Every engine script except `profile.py` calls `mlib.require_init(root)` and exits 2 if `monitor/profile.json` is missing.
- Log schema (`REQUIRED`/`LEVELS`/`STATUSES` in `logger.py`) is locked in code — this plan does not touch those constants. `last_commit_hash` is added the same way `branch` already exists: auto-populated, not part of `REQUIRED`, so old log entries without it stay valid (they just render without a commit chip).
- `monitor/logs/operations.mtr` is never hand-edited or reformatted by anything but `logger.py`.
- Reports are immutable snapshots and the `<style>` block is locked to `mlib.PALETTE_CSS` — this plan only fills a template placeholder, it does not touch the template's design.
- This repo has no automated test suite (standing project decision, confirmed by the user) — verification steps in this plan run scripts directly against fixture data and check stdout, the same manual pattern already used for every other engine script (see `CLAUDE.md`'s "Testing changes locally" section), not pytest.
- After any change under `plugins/monitor/skills/monitor/`, bump `version` in `plugins/monitor/.claude-plugin/plugin.json` (project rule) — done once, in the final task.

---

### Task 1: Auto-capture `last_commit_hash` in the log schema

**Files:**
- Modify: `plugins/monitor/skills/monitor/scripts/monitor_lib.py` (new `git_last_commit()`, mirrors existing `git_branch()`)
- Modify: `plugins/monitor/skills/monitor/scripts/logger.py` (auto-populate the field, render it in the log block — no new CLI flag, purely automatic)
- Modify: `plugins/monitor/skills/monitor/scripts/render_logs.py` (parse the new field as first-class, render it as a chip on the Logs page)

**Interfaces:**
- Produces: `monitor_lib.git_last_commit(root: Path) -> str` — short `HEAD` sha at call time, `""` outside a repo or in a repo with no commits yet (never raises, same contract as `git_branch`). Every entry dict produced by both `logger.log_operation()` and `render_logs.parse_log()` gains a `last_commit_hash` key (string, `""` when absent) — Task 2 (`search.py`) and Task 4 (report range) both read this key.

- [ ] **Step 1: Add `git_last_commit()` to `monitor_lib.py`**

In `plugins/monitor/skills/monitor/scripts/monitor_lib.py`, directly after the existing `git_branch()` function (ends around line 138), add:

```python
def git_last_commit(root: Path) -> str:
    """Short sha of HEAD at call time, or "" when unavailable (no repo, or a
    repo with no commits yet). Mirrors git_branch()'s never-raises contract."""
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5)
    except Exception:  # noqa: BLE001 — git missing/unusable is not an error here
        return ""
    sha = out.stdout.strip()
    return sha if out.returncode == 0 and sha else ""
```

- [ ] **Step 2: Auto-populate and render it in `logger.py`**

In `plugins/monitor/skills/monitor/scripts/logger.py`, in `render_entry()` (around line 59-74), add after the `branch` line:

```python
    if entry.get("last_commit_hash"):
        lines.append(f"last_commit_hash: {entry['last_commit_hash']}")
```

In `log_operation()` (around line 77-92), add a `last_commit_hash=None` parameter to the signature, auto-detect it the same way `branch` is auto-detected, and add it to the entry dict:

```python
def log_operation(root: Path, *, operation, tool, summary, status,
                  level="INFO", details="", files=None, task="", extra=None,
                  branch=None, last_commit_hash=None) -> None:
    if branch is None:
        branch = mlib.git_branch(root)
    if last_commit_hash is None:
        last_commit_hash = mlib.git_last_commit(root)
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3],
        "level": sanitize(level), "operation": sanitize(operation),
        "tool": sanitize(tool), "summary": sanitize(summary),
        "status": sanitize(status), "branch": sanitize(branch),
        "task": sanitize(task), "details": sanitize(details),
        "files": [sanitize(f) for f in (files or [])],
        "extra": {sanitize(k): sanitize(v) for k, v in (extra or {}).items()},
        "last_commit_hash": sanitize(last_commit_hash),
    }
```

No change to `main()` or the CLI — this is purely automatic, there is no `--last-commit-hash` flag, so nothing to remember to pass.

- [ ] **Step 3: Parse and render it in `render_logs.py`**

In `plugins/monitor/skills/monitor/scripts/render_logs.py`, in `parse_log()`'s entry-dict initializer (around line 82-84), add the key:

```python
        e = {"timestamp": timestamp, "level": level, "operation": operation,
             "tool": tool, "summary": summary, "status": status,
             "task": "", "files": [], "details": "", "branch": "", "extra": {},
             "last_commit_hash": ""}
```

In the field-parsing loop just below (around line 90-99), add a branch for the new key:

```python
            if key == "branch":
                e["branch"] = val
            elif key == "last_commit_hash":
                e["last_commit_hash"] = val
            elif key == "task":
```

In `_card()` (around line 131-132), render it as a chip right after the branch chip, reusing the existing `.toolchip` style (no new CSS needed):

```python
    if e.get("branch"):
        p.append("      " + mlib.branch_chip(e["branch"]))
    if e.get("last_commit_hash"):
        p.append(f'      <span class="toolchip">commit: {mlib.esc(e["last_commit_hash"])}</span>')
```

- [ ] **Step 4: Verify by hand against a real git repo**

`git_last_commit()` needs a real `.git`, so this fixture uses an actual repo instead of a plain directory:

```bash
cd /tmp && rm -rf commit-fixture && mkdir commit-fixture && cd commit-fixture
git init -q && git commit -q --allow-empty -m "seed"
mkdir -p monitor/logs monitor/scripts
cp /Users/ojaswi/Projects/monitor-tools/plugins/monitor/skills/monitor/scripts/*.py monitor/scripts/
echo '{"project": {"name": "fixture"}}' > monitor/profile.json
python3 monitor/scripts/logger.py --project-root . --operation test-op --tool Bash --summary "test entry" --status success
grep last_commit_hash monitor/logs/operations.mtr
git rev-parse --short HEAD
```

Expected: the `grep` line prints `last_commit_hash: <sha>` where `<sha>` matches the `git rev-parse --short HEAD` output on the line right after it.

- [ ] **Step 5: Clean up the fixture**

```bash
cd / && rm -rf /tmp/commit-fixture
```

- [ ] **Step 6: Commit**

```bash
git add plugins/monitor/skills/monitor/scripts/monitor_lib.py plugins/monitor/skills/monitor/scripts/logger.py plugins/monitor/skills/monitor/scripts/render_logs.py
git commit -m "feat: auto-capture last_commit_hash on every log entry"
```

---

### Task 2: `search.py` engine script

**Files:**
- Create: `plugins/monitor/skills/monitor/scripts/search.py`

**Interfaces:**
- Consumes: `monitor_lib.add_root_arg`, `monitor_lib.resolve_root`, `monitor_lib.require_init`, `monitor_lib.monitor_dir` (existing, `monitor_lib.py`); `render_logs.parse_log(text) -> list[dict]` (existing, `render_logs.py`) — entries are dicts with keys `timestamp, level, operation, tool, summary, status, task, files, details, branch, extra, last_commit_hash` (the last one added by Task 1; or `{"fragment": str}` for unparseable blocks, which this script must skip).
- Produces: `search(root: Path, query: str, *, branch: str | None = None, status: str | None = None, level: str | None = None, limit: int = 20) -> list[dict]` and `format_match(e: dict) -> str` — both importable, used by Task 3's command doc as the CLI contract.

- [ ] **Step 1: Write `search.py`**

```python
#!/usr/bin/env python3
"""Search monitor/logs/operations.mtr for entries matching a query.

Stdlib-only, plain-text output (no HTML page) — built for an agent to call
and read directly, like grep over the log. Reuses render_logs.parse_log() so
matching stays in sync with how entries are actually parsed.

Usage:
  python3 search.py --project-root <repo> --query "auth bug" \\
      [--branch <name>] [--status success|partial|failure] [--level LEVEL] \\
      [--limit N]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import monitor_lib as mlib
import render_logs


def _haystack(e: dict) -> str:
    parts = [e.get("operation", ""), e.get("tool", ""), e.get("summary", ""),
              e.get("task", ""), e.get("details", ""), e.get("branch", ""),
              e.get("last_commit_hash", "")]
    parts += [f"{k} {v}" for k, v in e.get("extra", {}).items()]
    return " ".join(parts).lower()


def search(root: Path, query: str, *, branch: str | None = None,
           status: str | None = None, level: str | None = None,
           limit: int = 20) -> list[dict]:
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


def format_match(e: dict) -> str:
    lines = [f"{e['timestamp']} {e['level']} [{e['operation']}] "
              f"({e['tool']}) {e['summary']} -- {e['status']}"]
    if e.get("branch"):
        lines.append(f"  branch:  {e['branch']}")
    if e.get("last_commit_hash"):
        lines.append(f"  commit:  {e['last_commit_hash']}")
    if e.get("task"):
        lines.append(f"  task:    {e['task']}")
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
                    help="Case-insensitive substring, matched across operation, "
                         "tool, summary, task, details, branch, commit, and extra fields.")
    ap.add_argument("--branch", default=None)
    ap.add_argument("--status", default=None, choices=("success", "partial", "failure"))
    ap.add_argument("--level", default=None, choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    ap.add_argument("--limit", type=int, default=20)
    args = ap.parse_args()
    root = mlib.resolve_root(args)
    mlib.require_init(root)
    matches = search(root, args.query, branch=args.branch, status=args.status,
                     level=args.level, limit=args.limit)
    if not matches:
        print(f"no matches for {args.query!r}")
        return 0
    print(f"{len(matches)} match(es) for {args.query!r}:\n")
    for e in matches:
        print(format_match(e))
        print("-" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Build a fixture log and verify by hand**

```bash
cd /tmp && rm -rf search-fixture && mkdir -p search-fixture/monitor/logs search-fixture/monitor/scripts
cp /Users/ojaswi/Projects/monitor-tools/plugins/monitor/skills/monitor/scripts/*.py search-fixture/monitor/scripts/
echo '{"project": {"name": "fixture"}}' > search-fixture/monitor/profile.json
cat > search-fixture/monitor/logs/operations.mtr <<'EOF'
2026-07-20 10:00:00,000 INFO [fix-bug] (Edit) Fixed the auth token refresh race condition -- success
branch:  main
last_commit_hash: abc1234
details: DECISION: used a mutex\nWHY: avoid double-refresh
================================================================================
2026-07-21 11:00:00,000 INFO [add-feature] (Write) Added CSV export -- success
branch:  feature/export
last_commit_hash: def5678
================================================================================
EOF
python3 search-fixture/monitor/scripts/search.py --project-root search-fixture --query "auth"
```

Expected output:
```
1 match(es) for 'auth':

2026-07-20 10:00:00,000 INFO [fix-bug] (Edit) Fixed the auth token refresh race condition -- success
  branch:  main
  commit:  abc1234
  details: DECISION: used a mutex\nWHY: avoid double-refresh
--------------------------------------------------------------------------------
```

Also verify a filter and a search-by-sha case:
```bash
python3 search-fixture/monitor/scripts/search.py --project-root search-fixture --query "export" --branch main
python3 search-fixture/monitor/scripts/search.py --project-root search-fixture --query "def5678"
```
Expected: the first prints `no matches for 'export'` (branch filter excludes the one real match, which is on `feature/export`); the second finds the CSV-export entry by its commit hash alone.

- [ ] **Step 3: Clean up the fixture**

```bash
rm -rf /tmp/search-fixture
```

- [ ] **Step 4: Commit**

```bash
git add plugins/monitor/skills/monitor/scripts/search.py
git commit -m "feat: add search.py engine script for querying operations.mtr"
```

---

### Task 3: `/monitor:search` command + registration

**Files:**
- Create: `plugins/monitor/commands/search.md`
- Modify: `plugins/monitor/skills/monitor/SKILL.md` (command table, around line 36-42)
- Modify: `plugins/monitor/commands/init.md` (injected command table at line 113-122, written into consumer `CLAUDE.md`/`AGENTS.md`)
- Modify: `CLAUDE.md` (repo root, "Repo layout" script list, around line 27, to list `search.py`)

**Interfaces:**
- Consumes: `search.py`'s CLI from Task 2 (`--query`, `--branch`, `--status`, `--level`, `--limit`).
- Produces: nothing new consumed by later tasks — this is a leaf command.

- [ ] **Step 1: Create `plugins/monitor/commands/search.md`**

```markdown
---
description: Search the monitor operations log for entries matching a query.
---

Search the monitor log for: **$ARGUMENTS**

**PRECONDITION — monitor must be initialised (check this FIRST).**
Verify `monitor/profile.json` exists (`test -f monitor/profile.json`). If it does
**not** exist, do **not** run any engine script or take any action. Reply with
exactly —

> ⚠️ monitor isn't initialised for this project yet. Run `/monitor:init` first, then re-run this command.

— and then STOP (end your turn immediately). Do not continue past this gate.

Read the **monitor** skill (`SKILL.md`) first. Then search via the engine:

```
python3 monitor/scripts/search.py --project-root . --query "<text>" \
    [--branch <name>] [--status success|partial|failure] [--level LEVEL] [--limit N]
```

If `$ARGUMENTS` isn't a clean query string (e.g. it's empty), ask the user
for one directly instead of guessing. Output is plain text, one block per
match, in the same shape as a log entry — read it directly. There is no HTML
results page: a search result is different every time it's run, while every
other monitor page is static and pre-built, so generating one here would be
both extra work and immediately stale. Relay the matches (or "no matches
found") to the user in your own words rather than dumping the raw output
verbatim.
```

- [ ] **Step 2: Add `/monitor:search` to the command table in `SKILL.md`**

Find this table (`plugins/monitor/skills/monitor/SKILL.md`, around line 36-42):

```markdown
| `/monitor:log` | Append one operation entry to the log. |
| `/monitor:report` | Author one HTML report + rebuild the Reports index. |
| `/monitor:record` | Log **and** (when code changed) report, in one step. |
| `/monitor:clean-logs <N>` | Delete the oldest N log entries; re-render Logs. |
| `/monitor:clean-reports <N>` | Delete the oldest N reports; re-render Reports + Dashboard. |
```

Add a `/monitor:search` row after `/monitor:record`:

```markdown
| `/monitor:log` | Append one operation entry to the log. |
| `/monitor:report` | Author one HTML report + rebuild the Reports index. |
| `/monitor:record` | Log **and** (when code changed) report, in one step. |
| `/monitor:search <query>` | Search the operations log by keyword; plain-text output. |
| `/monitor:clean-logs <N>` | Delete the oldest N log entries; re-render Logs. |
| `/monitor:clean-reports <N>` | Delete the oldest N reports; re-render Reports + Dashboard. |
```

- [ ] **Step 3: Add the same row to the injected command table in `init.md`**

Find this table (`plugins/monitor/commands/init.md`, around line 114-122):

```markdown
   | Command | Does |
   |---|---|
   | `/monitor:init` | First-time setup (idempotent). Run once per project. |
   | `/monitor:log` | Append one operation entry to the log. |
   | `/monitor:report` | Author one HTML report + rebuild the Reports index. |
   | `/monitor:record` | Log, and if code changed, report — in one step. |
   | `/monitor:update` | Re-detect + additively reconcile the profile, refresh assets. |
   | `/monitor:clean-logs <N>` | Delete the oldest N log entries; re-render Logs. |
   | `/monitor:clean-reports <N>` | Delete the oldest N reports; re-render Reports + Dashboard. |
```

Add the `/monitor:search` row after `/monitor:record`:

```markdown
   | Command | Does |
   |---|---|
   | `/monitor:init` | First-time setup (idempotent). Run once per project. |
   | `/monitor:log` | Append one operation entry to the log. |
   | `/monitor:report` | Author one HTML report + rebuild the Reports index. |
   | `/monitor:record` | Log, and if code changed, report — in one step. |
   | `/monitor:search <query>` | Search the operations log by keyword; plain-text output. |
   | `/monitor:update` | Re-detect + additively reconcile the profile, refresh assets. |
   | `/monitor:clean-logs <N>` | Delete the oldest N log entries; re-render Logs. |
   | `/monitor:clean-reports <N>` | Delete the oldest N reports; re-render Reports + Dashboard. |
```

- [ ] **Step 4: Add `search.py` to the repo-root `CLAUDE.md` script list**

Find this line (`CLAUDE.md`, around line 27):

```
      clean.py                      deletes oldest N logs, oldest N reports, re-renders affected pages
```

Add a line after it:

```
      clean.py                      deletes oldest N logs, oldest N reports, re-renders affected pages
      search.py                     greps operations.mtr by keyword + optional branch/status/level filters, plain-text output
```

- [ ] **Step 5: Commit**

```bash
git add plugins/monitor/commands/search.md plugins/monitor/skills/monitor/SKILL.md plugins/monitor/commands/init.md CLAUDE.md
git commit -m "feat: add /monitor:search command"
```

---

### Task 4: Report commit-range placeholder

**Files:**
- Modify: `plugins/monitor/commands/report.md`
- Modify: `plugins/monitor/commands/record.md` (the report step only)
- Modify: `plugins/monitor/skills/monitor/SKILL.md` (the `--details` / decision-capture convention section)

**Interfaces:**
- Consumes: `last_commit_hash` field from Task 1 (available on every log entry from this point forward, readable via `search.py` or `render_logs.parse_log()` for entries on the branch being reported).
- Produces: nothing new consumed by later tasks.

- [ ] **Step 1: Add commit-range guidance to `report.md`**

In `plugins/monitor/commands/report.md`, step 2 currently reads:

```markdown
2. Author the report from `monitor/reports/template.html` into
   `monitor/reports/<YYYY-MM-DD>-<slug>.html`. The template's design is fixed
   (`mlib.PALETTE_CSS`, identical across every project) — only fill in content.
   Fill every `{{ branch }}` placeholder with the
   branch the work was done on (`git rev-parse --abbrev-ref HEAD`). **Only the
```

Change it to also cover `{{ commit }}`:

```markdown
2. Author the report from `monitor/reports/template.html` into
   `monitor/reports/<YYYY-MM-DD>-<slug>.html`. The template's design is fixed
   (`mlib.PALETTE_CSS`, identical across every project) — only fill in content.
   Fill every `{{ branch }}` placeholder with the
   branch the work was done on (`git rev-parse --abbrev-ref HEAD`). Fill
   `{{ commit }}` with the range of commits this report covers, as
   `<first-short-sha>..<last-short-sha>` (e.g. `58e342a..bd3ecb7`) — the
   first commit unique to this branch's work through the current `HEAD`; if
   the report covers exactly one commit, use just that single short sha with
   no range. **Only the
```

(The rest of that step's paragraph — starting `text content changes...` — is unchanged; this only inserts the `{{ commit }}` sentence before it.)

- [ ] **Step 2: Add the same guidance to `record.md`'s report step**

In `plugins/monitor/commands/record.md`, step 2 ("**Report** — only if code changed..."), the sentence `Fill every {{ branch }} placeholder with the branch the work was done on.` becomes:

```markdown
Fill every `{{ branch }}` placeholder with the
   branch the work was done on, and `{{ commit }}` with the range of commits
   this report covers as `<first-short-sha>..<last-short-sha>` (or a single
   short sha if the report covers exactly one commit).
```

- [ ] **Step 3: Note the automatic `last_commit_hash` field in `SKILL.md`**

In `plugins/monitor/skills/monitor/SKILL.md`, find the sentence ending `see SKILL.md for the full convention` in the `--details` / decision-capture section (the one duplicated into `init.md`'s injected block — search for `DECISION:` in `SKILL.md` to locate it), and add a new sentence directly after that paragraph:

```markdown
Every log entry automatically records the git `HEAD` short sha at the moment
it's logged (`last_commit_hash`, captured by `logger.py` itself — no manual
step, works even for entries the user triggers by hand). It's searchable via
`/monitor:search --query <sha>` and is what reports use to fill their
`{{ commit }}` range.
```

- [ ] **Step 4: Commit**

```bash
git add plugins/monitor/commands/report.md plugins/monitor/commands/record.md plugins/monitor/skills/monitor/SKILL.md
git commit -m "docs: fill report {{ commit }} range from auto-captured commit hashes"
```

---

### Task 5: Version bump + plugin manifest description

**Files:**
- Modify: `plugins/monitor/.claude-plugin/plugin.json`

**Interfaces:**
- Consumes: nothing (final housekeeping task).
- Produces: nothing (leaf task).

- [ ] **Step 1: Bump the version and update the description**

In `plugins/monitor/.claude-plugin/plugin.json`, change:

```json
  "version": "1.9.0",
```

to:

```json
  "version": "1.10.0",
```

And in the `"description"` field, change:

```
Commands: /monitor:init, /monitor:log, /monitor:report, /monitor:record, /monitor:update, /monitor:clean-logs, /monitor:clean-reports.
```

to:

```
Commands: /monitor:init, /monitor:log, /monitor:report, /monitor:record, /monitor:search, /monitor:update, /monitor:clean-logs, /monitor:clean-reports.
```

- [ ] **Step 2: Verify the JSON is still valid**

```bash
python3 -c "import json; json.load(open('plugins/monitor/.claude-plugin/plugin.json'))" && echo OK
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add plugins/monitor/.claude-plugin/plugin.json
git commit -m "chore: bump monitor plugin version to 1.10.0 for /monitor:search"
```

---

## Self-Review Notes

- **Spec coverage:** auto-captured commit hash on every log entry (Task 1 — supersedes the earlier manual `--set commit=` approach per user feedback), search function (Task 2 + 3), `/monitor:search` skill/command (Task 3), commit hashes in reports (Task 4). All asks from the brainstorming conversation are covered.
- **Placeholder scan:** no TBD/TODO — every step has literal file content or an exact command.
- **Type consistency:** `search()`'s signature (`branch`, `status`, `level`, `limit` keyword args) matches what `search.py`'s `main()` passes and what `search.md` documents as CLI flags. `last_commit_hash` is spelled identically across `monitor_lib.py`, `logger.py`, `render_logs.py`, and `search.py`.
- **Scope:** deliberately excludes the Logs-page branch-filter UI and full-text search of report HTML — neither was part of this request; noted as available follow-ups if wanted later, not built here to avoid scope creep. Deliberately does not add a `--last-commit-hash` CLI override to `logger.py` — auto-only, no flag to forget, per the request that even user-triggered manual logging captures it for free.
