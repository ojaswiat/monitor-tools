<!-- monitor:start -->
## monitor — operations log, tasks, and reports (dogfooded on this repo)

This repo has **monitor** installed on itself via `./install-monitor.sh .`
(engine + commands under `.claude/`, generated data under the top-level
`monitor/`) — the same workflow this repo ships to consumers, used here to
develop the plugin itself. `monitor/` is committed like any consumer
project's — the installed engine copy under `.claude/` stays gitignored
(a project-local install of the portable source under `plugins/monitor/`).
Rules for using it live in `.claude/skills/monitor/SKILL.md` — read it
before running any command below.

The three tracked entities have a clear split: **logs** are the continuous
record (every operation, including the start and end of bigger ones);
**tasks** mark only the start and close of a multi-step unit of work, not
the steps in between; **reports** are a one-per-branch summary snapshot.

### Logging

**Use case:** the continuous audit trail. Every state-changing operation
gets an entry — this is what lets a different agent (or a later session)
resume cold without re-deriving what happened or why.

**How to use (hard rule — not optional, no exceptions):**
- Run `/monitor:log` or `/monitor:record` after every state-changing
  operation, including small ones (one file edit, one command run, one
  config tweak). This is default behavior, not something to wait for
  permission on — the operation itself is the trigger, and the user
  staying silent about monitor is not a signal to skip it. A tight
  edit+build+commit can be one entry, but don't skip logging just
  because the change was small.
- On failure, log it anyway with `status=failure` and the real error —
  don't skip logging just because the operation didn't succeed.
- For real decisions, log the reasoning, not just the outcome. In
  `--details`, capture (whichever apply) `DECISION:` what was chosen,
  `WHY:` alternatives considered and rejected, `ARCHITECTURE:` what
  structurally changed, `NEXT:` the immediate next step, `GAPS:` known
  issues/TODOs, `ASSUMPTIONS:` anything unverified. A trivial mechanical
  edit just needs `--summary`, no `--details`. Reports pull their
  **Decisions & Rationale** and **Gaps & Assumptions** sections straight
  from these fields — see `SKILL.md` for the full convention.
- Only an explicit user instruction to skip logging for a specific
  action overrides this rule — and that override applies to the single
  action it was given for, not the rest of the session.

### Task Tracking

**Use case:** marks only the initial and final stages of a multi-step
unit of work — the boundary, not the in-between (logging already covers
that, cross-referenced back to the task via `--task-id`). Distinct from
logging: logs are continuous, tasks are start/close bookends around a
unit of work large enough to need one.

**How to use (hard rule — not optional, no exceptions):**
- Start a task (`/monitor:task-start "<title>"`) before beginning any
  unit of work with more than one step, update it
  (`/monitor:task-update <id>`) as status changes, and close it
  (`/monitor:task-close <id>`) on completion or failure — same hard-rule
  treatment as logging, not something to ask about first.
- Only an explicit user instruction to skip task-tracking for a specific
  action overrides this rule — and that override applies to the single
  action it was given for, not the rest of the session.
- monitor also nudges when it notices a plan/spec markdown file get
  written (any `plans/` or `specs/` directory) with no task currently
  open — a `[Warn!] Monitor: no task tracked for recent plan/spec work`
  line, informational and non-blocking. It is a heuristic, not a
  guarantee: it does not fire for work that never touches such a file,
  and does not know whether an already-open task actually covers new
  work — start one whenever real multi-step work begins, don't wait for
  the nudge.

### Reporting

**Use case:** one branch-level summary snapshot — decisions, rationale,
files touched, gaps — generated before merge so a reviewer (human or
agent) can read the whole branch's reasoning in one place instead of
piecing it together from commits.

**How to use (default judgment — apply as usual, not forced every time):**
- Generate a report before every merge if the branch has code changes not
  yet covered by one — do this by default when asked to merge, don't wait
  to be asked for a report separately.
- After code changes generally, write a report with `/monitor:report` (or
  via `/monitor:record`) — never report a discussion or doc-only tweak.
- Reports render an HTML page and cost more to generate than a log entry
  — apply judgment on *when* one is warranted (per the two rules above),
  rather than authoring one for every single logged operation.

### Search

**Use case:** find past decisions and context across logs, reports, and
tasks without reading files by hand — the mechanism that makes the
audit trail actually useful instead of just accumulating.

**How to use:**
- `/monitor:search <query>` — case-insensitive substring search.
  `--scope logs|reports|tasks|all` picks the source (default `all`,
  grouped by source in the output); `--branch`/`--status`/`--level`
  filter log matches.

### Cleanup

**Use case:** prune old entries once the Dashboard grows long — logs,
reports, and tasks are each pruned independently, oldest first.

**How to use:**
- `/monitor:clean-logs <N>` — delete the oldest N log entries.
- `/monitor:clean-reports <N>` — delete the oldest N reports.
- `/monitor:clean-tasks <N>` — delete the oldest N tasks (all their
  events).

### Status

**Use case:** a quick "what's going on" snapshot — open tasks, recent
activity, pending items, next steps — without reading logs/tasks/git by
hand. Chat-only: it never writes a report, dashboard entry, or any other
file.

**How to use:**
- `/monitor:status` — prints straight to chat. Every fact comes from
  existing data (open tasks, the last few log entries, `NEXT:`/`GAPS:`/
  `ASSUMPTIONS:` fields already recorded in those entries, the
  pending-state gate, and recent git history) — nothing is inferred or
  guessed.

### Commands

| Command | Does |
|---|---|
| `/monitor:init` | First-time setup (idempotent). Already run once here. |
| `/monitor:log` | Append one operation entry to the log. |
| `/monitor:report` | Author one HTML report + rebuild the Reports index. |
| `/monitor:record` | Log, and if code changed, report — in one step. |
| `/monitor:search <query>` | Search logs, reports, and tasks by keyword; plain-text output. |
| `/monitor:status` | Show open tasks, recent activity, pending items, and next steps directly in chat. Never writes a file. |
| `/monitor:update` | Re-detect + additively reconcile the profile, refresh assets. |
| `/monitor:task-start "<title>"` | Start a lifecycle-tracked task; prints its `task_id`. |
| `/monitor:task-update <id>` | Append a status/metrics update to an open task. |
| `/monitor:task-close <id>` | Close a task with a terminal status (success/failed/cancelled). |
| `/monitor:clean-logs <N>` | Delete the oldest N log entries; re-render Logs. |
| `/monitor:clean-reports <N>` | Delete the oldest N reports; re-render Reports + Dashboard. |
| `/monitor:clean-tasks <N>` | Delete the oldest N tasks (all their events); re-render Tasks + Dashboard. |

### Rules

- Every command except `/monitor:init` requires `monitor/profile.json` to
  exist — it fails fast otherwise. Run init first if it's missing.
- Never hand-edit `monitor/logs/operations.mtr` — always go through
  `logger.py` (via `/monitor:log` or `/monitor:record`); hand-edits desync
  the log from the rendered Logs page.
- Reports are immutable snapshots — never rewrite an old report when the
  template changes; only new reports pick up new sections.
- A task is a separate tracked entity, not a field on a log entry — track
  it with `/monitor:task-start`/`task-update`/`task-close` (never hand-edit
  `monitor/tasks/tasks.mtr`), and cross-reference it from log entries with
  `logger.py --task-id <id>`.
- `monitor/profile.json` evolves additively only — `/monitor:update` adds
  detected fields, never removes or renames existing ones.
- After a commit, merge, or rebase, a `[Warn!] Monitor: Pending logs and
  report...` line may appear at the start of a turn — monitor's
  pending-state gate reporting unlogged/unreported work, not a bug.
  Answer Y to record it now, or N to defer. A separate
  `[Warn!] Monitor: no task tracked for recent plan/spec work` line (see
  Task Tracking above) works the same way but is purely informational,
  never a Y/N question.
- Never record development history, version changelogs, or reasoning
  leakage in any user-facing documentation (READMEs, skill files, this
  file, generated docs).
<!-- monitor:end -->
