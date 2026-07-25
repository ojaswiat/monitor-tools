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
  edit just needs `--summary`, no `--details`.

**Commands:**
| Command | Does |
|---|---|
| `/monitor:init` | First-time setup (idempotent). Already run once here. |
| `/monitor:log` | Append one operation entry to the log. |
| `/monitor:report` | Author one HTML report + rebuild the Reports index. |
| `/monitor:record` | Log, and if code changed, report — in one step. |
| `/monitor:search <query>` | Search the operations log by keyword; plain-text output. |
| `/monitor:update` | Re-detect + additively reconcile the profile, refresh assets. |
| `/monitor:clean-logs <N>` | Delete the oldest N log entries; re-render Logs. |
| `/monitor:clean-reports <N>` | Delete the oldest N reports; re-render Reports + Dashboard. |

**Rules:**
- Every command except `/monitor:init` requires `monitor/profile.json` to
  exist — it fails fast otherwise.
- Never hand-edit `monitor/logs/operations.mtr` — always go through
  `logger.py` (via `/monitor:log` or `/monitor:record`).
- Reports are immutable snapshots — never rewrite an old report when the
  template changes; only new reports pick up new sections.
- `monitor/profile.json` evolves additively only — `/monitor:update` adds
  detected fields, never removes or renames existing ones.
<!-- monitor:end -->
