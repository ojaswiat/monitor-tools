# tasks feature — design spec

## Summary

Add a third first-class entity to monitor, alongside logs and reports:
**tasks** — a lifecycle-tracked unit of agent work with self-reported
metrics (tokens, credits, cost, skills used, tools called). Implementation
mirrors the existing log system: an append-only text file
(`monitor/tasks/tasks.mtr`), an engine script that validates and writes to
it (`tasks.py`), and a render script that regenerates a paginated HTML view
(`render_tasks.py` → `monitor/tasks/index.html`), linked from the Dashboard
alongside Reports and Logs.

## Why

Logs record discrete operations; reports summarize a branch's worth of
completed work. Neither tracks a unit of work *while it's in flight*, with a
status that can be open, blocked, or waiting on approval, and metrics that
accumulate as it proceeds. Tasks fill that gap — a lightweight, queryable
record of what the agent is working on right now and what it cost.

## Non-goals (v1)

- No automatic instrumentation. The engine is stdlib Python with no access
  to the real session transcript — it cannot introspect actual token counts,
  which skills fired, or which tools ran. All metrics are self-reported by
  the agent via CLI flags, the same trust model `--details` already uses.
- Open tasks do **not** feed the pending-state hook gate (`pending.py`).
  That gate is scoped to unlogged commits/unreported branches; extending it
  to "you have an open task" is a plausible future extension, not v1 scope.
- No new companion plugin. Integration with existing tools (this harness's
  `TaskCreate`/`TaskUpdate`/`TaskGet`, `superpowers:subagent-driven-development`)
  is documented guidance in `SKILL.md`, not new code.

## Data model

### `monitor/tasks/tasks.mtr`

Same physical format as `monitor/logs/operations.mtr`: newest-first,
`"=" * 80`-separated blocks, one header line plus `key: value` lines below
it. Every lifecycle action (start / update / close) writes its own block —
the file is a pure event log, never mutated in place.

Header line shape (mirrors `logger.py`'s `render_entry`):
```
<timestamp> <LEVEL> [<event>] (<task_id>) <summary> -- <status>
```
where `<event>` is one of `task-start` / `task-update` / `task-close`.

Fields (`key: value` lines, all sanitized the same way `logger.py` sanitizes
today — control chars stripped, real newlines flattened):
- `task_id` (also embedded in the header's parens) — short id, generated on
  `task-start` the same way a git short sha looks: 8 lowercase hex chars
  from `uuid4().hex[:8]`, collision-rechecked against existing ids in the
  file (regenerate on collision — the file is small enough this is cheap).
- `title` — present on `task-start` only; the task's human-readable name.
- `status` — one of the status enum below. Required on every event.
- `tokens`, `credits`, `cost` — optional numeric fields, present when the
  agent supplies them on that event.
- `skills_used`, `tools_called` — optional comma-separated lists, present
  when supplied on that event.
- `branch` — auto-detected the same way `logger.py` does
  (`mlib.git_branch()`), present on every event.
- `last_commit_hash` — auto-captured the same way `logger.py` does
  (`mlib.git_last_commit()`), present on every event.
- `details` — optional free text, same `format_list_block` convention as
  logs (`\n`-per-point, rendered as a real list).

### Status enum

```
open, in_progress, needs_approval, needs_retry, blocked, success, failed, cancelled
```
`open`/`in_progress`/`needs_approval`/`needs_retry`/`blocked` are
non-terminal (task-update only). `success`/`failed`/`cancelled` are
terminal (task-close only) — once written, no further events reference that
`task_id` (the engine does not enforce this technically in v1; SKILL.md
documents it as the convention, matching how `operations.mtr` documents
append-only-through-logger.py by convention, not filesystem lock).

### Metrics aggregation

`render_tasks.py` groups blocks by `task_id`, sums `tokens`/`credits`/`cost`
across every event for that id (missing values treated as 0), and unions
`skills_used`/`tools_called` across events (dedup, preserve first-seen
order) for the card's totals. The card's status is whatever the
most-recent event for that id set (blocks are newest-first, so the first
block encountered per id wins).

## Engine

### `tasks.py` (new, mirrors `logger.py`)

- `STATUSES = ("open", "in_progress", "needs_approval", "needs_retry", "blocked", "success", "failed", "cancelled")`
- `NONTERMINAL = STATUSES[:5]`, `TERMINAL = STATUSES[5:]`
- `new_task_id(root) -> str` — generates and collision-checks against
  existing ids parsed from `tasks.mtr`.
- `start_task(root, *, title, status="open", ...) -> str` (returns the new
  `task_id`, printed to the agent so it can be passed to update/close).
- `update_task(root, *, task_id, status, ...)` — validates `task_id` exists
  in the file and `status in NONTERMINAL` (reject terminal status on
  update — that's what `close_task` is for).
- `close_task(root, *, task_id, status, ...)` — validates `status in
  TERMINAL`.
- Shared `sanitize()`/field-writing logic reused from `logger.py` (extract
  the sanitize helper into `monitor_lib.py` if that avoids duplicating it —
  implementation detail for the plan, not the spec).
- Calls `render_tasks.render(root)` after every write, same
  best-effort-refresh pattern `logger.py` uses for `render_logs.py`.
- CLI: `python3 tasks.py start --title "..." [--status ...] [metrics]`,
  `python3 tasks.py update --task-id <id> --status ... [metrics]`,
  `python3 tasks.py close --task-id <id> --status success|failed|cancelled [metrics]`.

### `render_tasks.py` (new, mirrors `render_logs.py`)

- Parses `tasks.mtr` the same tolerant way `render_logs.py` parses
  `operations.mtr` (fragment-skip on corrupt blocks, warns to stderr, never
  drops the rest of the file).
- Groups into per-`task_id` cards: title, current status (tag styled like
  Logs' pass/warn/fail — new tag classes for the 8 statuses, reusing
  `mlib.PALETTE_CSS`'s existing tag color set: `success`→pass,
  `failed`→fail, `cancelled`→fail, `needs_approval`/`needs_retry`/`blocked`→warn,
  `open`/`in_progress`→info), aggregated metrics row, and a collapsible
  timeline of every event for that id (timestamp + status + summary, oldest
  to newest).
- Paginated the same way Logs/Reports are (`mlib.PAGE_SIZE`, `page()`,
  `pagination_nav()`), one card per task per page.
- Writes `monitor/tasks/index.html` / `page-N.html`.

### `logger.py` changes

- Remove `--task` (free-text label) entirely — this is what step 2 of the
  brainstorm concluded: tasks becomes an independent entity, not a string
  field parked on log entries.
- Add `--task-id` (optional) — a pure foreign key, no validation against
  `tasks.mtr` required (a log entry can reference a task that predates this
  feature's rollout or has since aged out of a `clean-logs` run; failing
  hard on a dangling reference would fight the immutability of both files).
  Stored as a `task_id: <value>` line, rendered on the Logs page as a chip
  (same visual treatment `last_commit_hash` already gets) that could link to
  the task's card in a later iteration — v1 just displays it as text.

### Dashboard / `monitor_lib.py` changes

- `tabnav()` gains a third tab: Tasks (alongside Reports, Logs).
- Dashboard KPI row gains "Open tasks" (count of ids whose most-recent
  status is non-terminal).
- No changes to `PALETTE_CSS` structurally — only new tag-color mappings for
  the additional statuses, using colors already defined (pass/warn/fail/info).

### `clean.py` changes

- New `--tasks <N>` flag, same shape as `--logs`/`--reports`: deletes the
  oldest N *task ids* (all their events, not just the oldest N raw blocks —
  deleting only some of a task's events would leave a card with missing
  history) and re-renders.

## Commands

Three new command files, `plugins/monitor/commands/task-start.md`,
`task-update.md`, `task-close.md` — same shape as `log.md`/`report.md`:
precondition gate on `monitor/profile.json`, read `SKILL.md` first, run the
engine, relay the result (and for `task-start`, relay the generated
`task_id` prominently — the agent needs it for every subsequent
update/close call).

## SKILL.md additions

New `## Tasks` section (parallel to the existing `## Logging` /
`## Reporting` sections), covering: the file layout addition, the status
enum and terminal/non-terminal split, the metrics-are-self-reported caveat,
and an **integration points** subsection:
- This harness's own `TaskCreate`/`TaskUpdate`/`TaskGet` calls map
  naturally to `task-start`/`task-update`/`task-close` — when the agent is
  already tracking a task with the harness's native tool, mirror the same
  lifecycle into monitor so it's recoverable from the log/report system
  too, not just the harness's own ephemeral task state.
- `superpowers:subagent-driven-development`'s per-task dispatch loop
  (ledger file, one task per implementer round) maps the same way — a
  `task-start` when a task's implementer is dispatched, `task-update` on
  each fix-loop round, `task-close` when the ledger marks it done.

Also update the `## Where things live` tree and `## Common mistakes` table
(new row: "Putting task info in `--details` on a log entry" → "Use
`/monitor:task-start`/`update`/`close` — tasks are a separate tracked
entity now, not a log field").

## Testing

No test suite in this repo (per `CLAUDE.md`). Validate the same way every
other engine change is validated: `./install-monitor.sh` into a scratch
project, run `/monitor:task-start`/`update`/`close` there, inspect
`tasks.mtr` and the rendered Tasks page directly.

## Open questions for the plan (not the spec)

None — the design as approved covers every field, status, and file this
needs. Sequencing (which script first, how to extract shared `sanitize()`
without breaking `logger.py`) is an implementation-plan concern.
