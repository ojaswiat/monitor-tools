# Monitor Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `search.py` engine script + `/monitor:search` command so an agent can grep the operations log for past decisions instead of paging through static HTML by hand, and thread commit hashes through log entries and reports for traceability.

**Architecture:** `search.py` is a new stdlib-only engine script that reuses `render_logs.parse_log()` (already the canonical entry parser) to filter `monitor/logs/operations.mtr` by a case-insensitive substring query plus optional `--branch`/`--status`/`--level` filters, printing plain-text matches — no new HTML page, since a search result is dynamic and every other monitor page is static/pre-built. Commit hashes are threaded in two places using the engine's existing extensibility, not new schema fields: log entries get one via the existing `--set commit=<sha>` extra-field mechanism (agent's call, when a log entry follows a commit), and reports fill the existing (currently-unused) `{{ commit }}` template placeholder with a `first..last` short-sha range covering the report.

**Tech Stack:** Python 3 stdlib only (matches the rest of the engine — no new dependencies).

## Global Constraints

- Engine scripts are stdlib-only Python 3, no third-party dependencies (project-wide rule, `CLAUDE.md`).
- Every engine script except `profile.py` calls `mlib.require_init(root)` and exits 2 if `monitor/profile.json` is missing.
- Log schema (`REQUIRED`/`LEVELS`/`STATUSES` in `logger.py`) is locked in code — this plan does not modify it; commit tracking goes through the existing `--set key=value` extra-field mechanism instead.
- `monitor/logs/operations.mtr` is never hand-edited or reformatted by anything but `logger.py`.
- Reports are immutable snapshots and the `<style>` block is locked to `mlib.PALETTE_CSS` — this plan only fills a template placeholder, it does not touch the template's design.
- This repo has no automated test suite (standing project decision, confirmed by the user) — verification steps in this plan run scripts directly against fixture data and check stdout, the same manual pattern already used for every other engine script (see `CLAUDE.md`'s "Testing changes locally" section), not pytest.
- After any change under `plugins/monitor/skills/monitor/`, bump `version` in `plugins/monitor/.claude-plugin/plugin.json` (project rule) — done once, in the final task.

---

### Task 1: `search.py` engine script

**Files:**
- Create: `plugins/monitor/skills/monitor/scripts/search.py`

**Interfaces:**
- Consumes: `monitor_lib.add_root_arg`, `monitor_lib.resolve_root`, `monitor_lib.require_init`, `monitor_lib.monitor_dir` (all existing, `monitor_lib.py`); `render_logs.parse_log(text) -> list[dict]` (existing, `render_logs.py`) — entries are dicts with keys `timestamp, level, operation, tool, summary, status, task, files, details, branch, extra` (or `{"fragment": str}` for unparseable blocks, which this script must skip).
- Produces: `search(root: Path, query: str, *, branch: str | None = None, status: str | None = None, level: str | None = None, limit: int = 20) -> list[dict]` and `format_match(e: dict) -> str` — both importable, used by Task 2's command doc as the CLI contract and available for reuse if a future script needs them.

- [ ] **Step 1: Write `search.py`**

```python
#!/usr/bin/env python3
"""Search monitor/logs/operations.mtr for entries matching a query.

Stdlib-only, plain-text output (no HTML page) — built for an agent to call
and read directly, like grep over the log. A search result is dynamic and
every other monitor page is static/pre-built, so this deliberately doesn't
generate one. Reuses render_logs.parse_log() so matching stays in sync with
how entries are actually parsed.

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
              e.get("task", ""), e.get("details", ""), e.get("branch", "")]
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
                         "tool, summary, task, details, branch, and extra fields.")
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
details: DECISION: used a mutex\nWHY: avoid double-refresh
commit: abc1234
================================================================================
2026-07-21 11:00:00,000 INFO [add-feature] (Write) Added CSV export -- success
branch:  feature/export
================================================================================
EOF
python3 search-fixture/monitor/scripts/search.py --project-root search-fixture --query "auth"
```

Expected output:
```
1 match(es) for 'auth':

2026-07-20 10:00:00,000 INFO [fix-bug] (Edit) Fixed the auth token refresh race condition -- success
  branch:  main
  commit: abc1234
  details: DECISION: used a mutex\nWHY: avoid double-refresh
--------------------------------------------------------------------------------
```

Also verify a filter and a no-match case:
```bash
python3 search-fixture/monitor/scripts/search.py --project-root search-fixture --query "export" --branch main
python3 search-fixture/monitor/scripts/search.py --project-root search-fixture --query "nonexistent-keyword"
```
Expected: the first prints `no matches for 'export'` (branch filter excludes the one real match, which is on `feature/export`); the second prints `no matches for 'nonexistent-keyword'`.

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

### Task 2: `/monitor:search` command + registration

**Files:**
- Create: `plugins/monitor/commands/search.md`
- Modify: `plugins/monitor/skills/monitor/SKILL.md` (command table, around line 36-42)
- Modify: `plugins/monitor/commands/init.md` (injected command table at line 113-122, written into consumer `CLAUDE.md`/`AGENTS.md`)
- Modify: `CLAUDE.md` (repo root, "Repo layout" script list, around line 27, to list `search.py`)

**Interfaces:**
- Consumes: `search.py`'s CLI from Task 1 (`--query`, `--branch`, `--status`, `--level`, `--limit`).
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

### Task 3: Commit-hash threading (log entries + report template)

**Files:**
- Modify: `plugins/monitor/commands/log.md`
- Modify: `plugins/monitor/commands/record.md` (both the log step and the report step)
- Modify: `plugins/monitor/commands/report.md`
- Modify: `plugins/monitor/skills/monitor/SKILL.md` (the `--details` convention section, to note the `commit` extra field)

**Interfaces:**
- Consumes: `logger.py`'s existing `--set key=value` flag (no code change needed — this task is documentation-only); `render_report.py`'s existing `{{ commit }}` placeholder in `reports/template.html` (already emitted by `render_template()` in `render_report.py:136`, currently never filled by any command — this task starts filling it).
- Produces: nothing new consumed by later tasks.

- [ ] **Step 1: Add commit-hash guidance to `log.md`**

In `plugins/monitor/commands/log.md`, after the existing paragraph that ends with `pass --branch <name> only to override it.`, add:

```markdown
If this entry follows a `git commit` (i.e. logging what a commit did), also
pass `--set commit=<short-sha>` (`git rev-parse --short HEAD`) so the entry
is traceable back to the exact commit and searchable by it via
`/monitor:search`. Skip it for entries that aren't tied to a specific commit
(e.g. a pre-commit decision, a failed attempt).
```

- [ ] **Step 2: Add the same guidance to `record.md`'s log step**

In `plugins/monitor/commands/record.md`, in step 1 ("**Log** the operation via the engine..."), after the sentence ending `pass --branch <name> only to override it.`, add the identical paragraph from Step 1 above.

- [ ] **Step 3: Add commit-range guidance to `report.md`**

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

- [ ] **Step 4: Add the same guidance to `record.md`'s report step**

In `plugins/monitor/commands/record.md`, step 2 ("**Report** — only if code changed..."), the sentence `Fill every {{ branch }} placeholder with the branch the work was done on.` becomes:

```markdown
Fill every `{{ branch }}` placeholder with the
   branch the work was done on, and `{{ commit }}` with the range of commits
   this report covers as `<first-short-sha>..<last-short-sha>` (or a single
   short sha if the report covers exactly one commit).
```

- [ ] **Step 5: Note the `commit` extra field in `SKILL.md`**

In `plugins/monitor/skills/monitor/SKILL.md`, find the sentence ending `see SKILL.md for the full convention` in the `--details` / decision-capture section (the one duplicated into `init.md`'s injected block — search for `DECISION:` in `SKILL.md` to locate it), and add a new sentence directly after that paragraph:

```markdown
When a log entry follows a commit, pass `--set commit=<short-sha>` — it's
the same general-purpose extra-field mechanism as any other `--set`, not a
schema change, and makes the entry traceable via `/monitor:search --query
<sha>` and visible in its `extra` chips on the Logs page.
```

- [ ] **Step 6: Commit**

```bash
git add plugins/monitor/commands/log.md plugins/monitor/commands/record.md plugins/monitor/commands/report.md plugins/monitor/skills/monitor/SKILL.md
git commit -m "docs: thread commit hashes through log entries and report template"
```

---

### Task 4: Version bump + plugin manifest description

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

- **Spec coverage:** search function (Task 1 + 2), `/monitor:search` skill/command (Task 2), commit hashes in reports (Task 3 Steps 3-4), plus the log-entry-side commit traceability the user's chosen option implied (Task 3 Steps 1-2, 5). All three asks from the brainstorming conversation are covered.
- **Placeholder scan:** no TBD/TODO — every step has literal file content or an exact command.
- **Type consistency:** `search()`'s signature (`branch`, `status`, `level`, `limit` keyword args) matches what `search.py`'s `main()` passes and what `search.md` documents as CLI flags.
- **Scope:** deliberately excludes the Logs-page branch-filter UI and full-text search of report HTML — neither was part of this request; noted as available follow-ups if wanted later, not built here to avoid scope creep.
