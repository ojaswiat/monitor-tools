# Follow-up fixes — design spec

## Summary

Five independent fixes/additions to `monitor`, grouped into one implementation
pass on branch `feat/followup-fixes`:

1. Open tasks feed the pending-state hook gate.
2. `clean --tasks`'s "oldest N" sorts by real creation time, not last-activity.
3. A pytest-based test suite for the engine's Python scripts, split into
   `test-unit` and `test-integration` skills; `test-e2e` stays as-is (name
   constraint: only a real Claude Code *plugin* gets colon-namespaced names
   like `monitor:log` — a plain project skill under `.claude/skills/` is
   always listed by its flat folder name, so `test-e2e`/`test-unit`/
   `test-integration` are the three skill names, no colon).
4. `search.py` covers reports and tasks, not just logs; a small client-side
   grep box on the Dashboard page (the one narrow, explicit exception to
   monitor's "no JS" rule — every other page stays script-free).
5. Report template gains real `date_created`/`last_modified` placeholders,
   both filled once at authoring time (reports are immutable snapshots —
   neither field ever changes after a report is written).

## 1. Open tasks in the pending-hook gate

**Current behavior:** `pending.py hook-user-prompt-submit` warns only about
unlogged commits (`pending_logs`) and unreported branches (`pending_report`).

**Change:** on every `hook-user-prompt-submit` call, also read
`monitor/tasks/tasks.mtr`, compute which `task_id`s' most recent status is
non-terminal (`open`/`in_progress`/`needs_approval`/`needs_retry`/`blocked`
— reuse `render_tasks.group_tasks()`/`NONTERMINAL`), and if any exist,
append them to the same warning message: one line per open task
(`task_id` + title + current status). No time threshold — symmetric with
how `pending_logs`/`pending_report` already work (present every turn,
unconditionally, until resolved). This is a read-only addition to the
warning text; it does not write anything new to `.pending.json` — open
tasks aren't "cleared" by an action the way a log/report is, they're
cleared by the agent eventually running `/monitor:task-close`.

## 2. `clean --tasks` creation-order fix

**Current behavior:** `clean_tasks()` calls `render_tasks.group_tasks()`,
which orders groups by first-event-encountered in the newest-first file —
i.e. by most recent activity, not creation.

**Change:** `group_tasks()` (or a `clean.py`-local helper) additionally
tracks, per task_id, the timestamp of its `task-start` event specifically
(not just "first event seen"). `clean_tasks()` sorts ascending by that
creation timestamp to determine the oldest N for deletion. A task with no
`task-start` event in the retained window (already partially cleaned in a
prior run) falls back to its earliest known event's timestamp — never
crashes on missing data.

## 3. Python test suite + skill split

**Framework:** pytest, dev-only dependency — a `requirements-dev.txt` at
the repo root (`pytest>=8`), never referenced by the shipped engine or
`install-monitor.sh`. The engine itself stays stdlib-only; this is
tooling to develop it with, not something that ships.

**Layout:**
```
tests/
  unit/           one function/behavior at a time, no subprocess/install flow
    test_sanitize.py
    test_logger.py
    test_tasks.py
    test_render_logs.py
    test_render_tasks.py
    test_render_report.py
    test_search.py
    test_pending.py
    test_clean.py
  integration/     exercises install-monitor.sh + multi-script flows end to end
    test_install_and_init.py
    test_log_then_report_flow.py
    test_task_lifecycle_flow.py
    test_pending_hook_flow.py
    test_search_flow.py
  conftest.py      shared tmp_path-based project-root fixture
```
Every test runs against a fresh `tmp_path` project root (via a shared
`conftest.py` fixture that copies the engine scripts in) — no test touches
this repo's own real `monitor/` directory or writes outside `tmp_path`.

**Coverage target (not exhaustive, the core contracts):** `sanitize()`
control-char/newline handling; `logger.py`/`tasks.py` `validate()` enum
enforcement (including the terminal/non-terminal split); the
`render_*.py` parse→render round trip on hand-written `.mtr` fixtures
(including the fragment-skip tolerance path); `search.py` matching across
all three sources (log/report/task) once item 4 lands; `pending.py`'s
write-on-commit / clear-on-log / clear-on-report / stale-open-tasks paths
(item 1); `clean.py`'s oldest-N logic for logs/reports/tasks including the
creation-order fix (item 2).

**Skills:** `.claude/skills/test-unit/SKILL.md` runs `pytest tests/unit`;
`.claude/skills/test-integration/SKILL.md` runs `pytest tests/integration`.
Both are thin — install `requirements-dev.txt` if pytest isn't already
importable, run the suite, relay pass/fail and any failures verbatim.
`test-e2e` is unchanged by this item (already covers the live dogfood
drill; explicitly kept manual/on-demand per your call, not automated here).

## 4. Search coverage + Dashboard grep box

**`search.py` extension:** new `--scope {logs,reports,tasks,all}` flag,
default `all`. `logs` is today's existing behavior unchanged. `reports`
greps each `monitor/reports/*.html`'s plain-text content (strip tags,
reuse the `_plain()`-style stripping already in `render_report.py`) for
the query, reporting matching report titles + a short excerpt. `tasks`
parses `tasks.mtr` the same way `render_tasks.parse_tasks()` does and
matches against `summary`/`details`/`title` fields, reporting matching
task_id + event + excerpt. Output stays plain text, one block per match,
same shape as today — a `## logs` / `## reports` / `## tasks` header line
separates sections when scope is `all` and more than one source has hits.

**Dashboard grep box:** a small, self-contained `<script>` block added
*only* to `monitor/index.html` (the Dashboard) — every other page (Logs,
Reports, Tasks, the report template) stays script-free, per your explicit
"narrow exception, this one feature only" decision. `render_dashboard()`
embeds a small JSON array at render time (log summaries + timestamps,
report titles + dates, task titles + status — not full `--details`/body
text, to keep the embedded payload small) and a plain `<input>` + result
`<ul>`; a few lines of vanilla JS filter the array on `input` and render
matching titles as links to the relevant page. No external libraries, no
build step, no network calls — same self-contained-HTML constraint every
other generated page already follows, just with one inline `<script>`
where those don't have one.

## 5. Report timestamp placeholders

`template.html` gains two new meta-chips next to the existing
`{{ branch }}`/`{{ commit }}`/`{{ status }}`: `{{ date_created }}` and
`{{ last_modified }}`. Both are filled once, at authoring time — reports
are immutable snapshots (never rewritten after creation), so neither
field is a live-updating value:
- `date_created`: the date the report's underlying work began (the
  agent's own judgment, same as today's `{{ date }}` — this is a second,
  distinct field, not a rename of it).
- `last_modified`: the moment the report was finalized — i.e. when
  `render_report.py --lock-report` ran (the last step before a report is
  ever indexed). `--lock-report` itself stamps this value in when it
  force-corrects the `<style>` block, so an authoring agent can't
  forget it.
- `{{ date }}` (the existing "Generated" chip) is unchanged — kept for
  backward compatibility with older reports that only have it.

## Non-goals

- No change to the 3-repo `/test-e2e` drill's own coverage — it already
  covers tasks/hooks/search as of the prior branch; this item's scope is
  purely the new pytest suite and the skill-naming split.
- No time-based staleness threshold for open tasks in the pending gate —
  symmetric with existing unconditional pending_logs/pending_report
  behavior, not a new invented policy.
- No colon-namespaced skill names (`test:e2e` etc.) — requires packaging
  as a real plugin, out of scope per your explicit decision to stay flat.

## Testing

The pytest suite itself IS the testing mechanism for items 1, 2, 4, and 5
(each gets unit + integration coverage per the layout above). Item 3
(the suite itself) is validated by the suite passing. The Dashboard grep
box (client-side JS) has no pytest coverage — verified manually by
generating a Dashboard and confirming the search box filters correctly in
a browser-rendered check (or via `Read`-ing the generated HTML and
confirming the embedded JSON/script are well-formed).
