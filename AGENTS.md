<!-- monitor:start -->
## monitor — operations log + reports (dogfooded on this repo)

This repo has **monitor** installed on itself via `./install-monitor.sh .`
(engine + commands under `.claude/`, generated data under the top-level
`monitor/`) — the same workflow this repo ships to consumers, used here to
develop the plugin itself. `monitor/` is generated local state, gitignored,
never committed from this repo — same rule as any consumer project's data
folder. Rules for using it live in `.claude/skills/monitor/SKILL.md` — read
it before running any command below.

**When to use it (defaults — no need to ask first):**
- **Log after every state-changing operation, including small ones** (one
  file edit, one command run, one config tweak) — run `/monitor:log` or
  `/monitor:record`. A tight edit+build+commit can be one entry, but don't
  skip logging just because the change was small.
- **Generate a report before every merge.** Before merging the current
  branch into its base branch, run `/monitor:report` (or `/monitor:record`)
  if the branch has code changes not yet covered by a report. Do this by
  default when asked to merge — don't wait to be asked for a report
  separately.
- After code changes generally — write a report with `/monitor:report` (or
  via `/monitor:record`). Never report a discussion or doc-only tweak.
- On failure, log it anyway with `status=failure` and the real error —
  don't skip logging just because the operation didn't succeed.
- **For real decisions, log the reasoning, not just the outcome.** In
  `--details`, capture (whichever apply) `DECISION:` what was chosen,
  `WHY:` alternatives considered and rejected, `ARCHITECTURE:` what
  structurally changed, `NEXT:` the immediate next step, `GAPS:` known
  issues/TODOs, `ASSUMPTIONS:` anything unverified. A trivial mechanical
  edit just needs `--summary`, no `--details`. Reports pull their
  **Decisions & Rationale** and **Gaps & Assumptions** sections straight
  from these fields — see `SKILL.md` for the full convention.

**Commands:**
| Command | Does |
|---|---|
| `/monitor:init` | First-time setup (idempotent). Already run once here. |
| `/monitor:log` | Append one operation entry to the log. |
| `/monitor:report` | Author one HTML report + rebuild the Reports index. |
| `/monitor:record` | Log, and if code changed, report — in one step. |
| `/monitor:search <query>` | Search the operations log by keyword; plain-text output. |
| `/monitor:update` | Re-detect + additively reconcile the profile, refresh assets. |
| `/monitor:task-start "<title>"` | Start a lifecycle-tracked task; prints its `task_id`. |
| `/monitor:task-update <id>` | Append a status/metrics update to an open task. |
| `/monitor:task-close <id>` | Close a task with a terminal status (success/failed/cancelled). |
| `/monitor:clean-logs <N>` | Delete the oldest N log entries; re-render Logs. |
| `/monitor:clean-reports <N>` | Delete the oldest N reports; re-render Reports + Dashboard. |
| `/monitor:clean-tasks <N>` | Delete the oldest N tasks (all their events); re-render Tasks + Dashboard. |

**Rules:**
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
  report...` line may appear at the start of a turn. That is monitor's
  pending-state gate reporting unlogged/unreported work, not a bug —
  answer Y to record it now, or N to defer.
- Never record development history, version changelogs, or reasoning
  leakage in any user-facing documentation (READMEs, skill files, this
  file, generated docs) — see "Editing the engine" above.
<!-- monitor:end -->
