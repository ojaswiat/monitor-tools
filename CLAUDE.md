# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A Claude Code **plugin marketplace** (`monitor-tools`) that distributes a single plugin, `monitor`: a portable, stdlib-only-Python logging + reporting workflow. Once installed into a target project, `monitor` maintains a project-local `monitor/` folder — a Dashboard linking a Reports page (self-contained HTML report per task/change) and a Logs page (rendered from a canonical `operations.mtr`, schema locked in code). No pip installs, no external assets, no hardcoded paths — Python 3 stdlib only.

This repo has no build step, package manager, or test suite. There is nothing to `npm install` or `pip install`. "Development" here means editing the plugin's skill scripts, commands, and templates directly.

## Repo layout

```
.claude-plugin/marketplace.json     catalog — registers the "monitor" plugin
install-monitor.sh                  fallback installer (copy without a marketplace)
plugins/monitor/
  .claude-plugin/plugin.json        plugin manifest (name, version, author) — bump version on release
  commands/*.md                     flat command files -> /monitor:init|log|report|record|search|update|clean-logs|clean-reports
  skills/monitor/
    SKILL.md                        the skill spec agents read to operate monitor
    scripts/                        the engine (all stdlib Python 3, no deps)
      monitor_lib.py                shared lib: project-root resolution, JSON IO, palette CSS, page/masthead chrome, pagination
      profile.py                    detects/reconciles monitor/profile.json (additive only)
      logger.py                     appends one entry to operations.mtr; schema locked in code (REQUIRED/LEVELS/STATUSES)
      render_logs.py                renders operations.mtr -> paginated logs/*.html
      render_report.py              regenerates reports/template.html, paginated reports/*.html, dashboard index.html
      clean.py                      deletes oldest N logs, oldest N reports, re-renders affected pages
      pending.py                    tracks monitor/.pending.json (unlogged commits, unreported merges/rebases); hook entrypoints back the pending-state gate
      search.py                     greps operations.mtr by keyword + optional branch/status/level filters, plain-text output
    assets/base_template.html       fallback report template
```

Commands (`plugins/monitor/commands/*.md`) are thin prompts for the agent; the actual logic lives in `skills/monitor/scripts/*.py`. As a plugin, commands resolve the engine via `$CLAUDE_PLUGIN_ROOT`; when copied manually via `install-monitor.sh`, they fall back to `.claude/skills/monitor`.

## Architecture — how the engine works when installed in a target project

- **Monitor has exactly two jobs: log and report.** It never detects a project's language, guesses build/test commands, or otherwise inspects what the project does — that's guessing, not recording. `monitor/profile.json` only auto-fills the project's directory name (for branding pages) plus the report KPI list; that's the entire "source of truth." If an agent needs real project orientation, that's what companion skills like `graphify` are for (see below), not monitor. The log schema lives in code in `logger.py` (`REQUIRED`/`LEVELS`/`STATUSES`), identical across every project — the same for a brand-new project as an old one. `/monitor:init` seeds the profile; `/monitor:update` reconciles it.
- **Reconciliation is strictly additive.** `profile.py` only ever adds detected keys/fields and bumps `profileVersion` — it never removes, renames, or overwrites existing keys (hand edits win). This is what keeps template upgrades backward compatible: the profile is always a superset of every prior version.
- **Init-gated.** Every script except `profile.py` calls `mlib.require_init()` and exits 2 if `monitor/profile.json` is missing. Commands must not run any other engine script before `/monitor:init`.
- **Path model.** Each script resolves its own project root via `Path(__file__).resolve().parents[2]` when it lives at `monitor/scripts/<x>.py` inside the target project (all scripts also accept `--project-root` to override). Never hardcode a project path.
- **Logs are append-only and canonical.** `logger.py` is the only writer of `monitor/logs/operations.mtr` (newest-first, `=`×80-separated blocks, validated against the locked in-code schema). Never hand-edit the log — `render_logs.py` regenerates the (paginated) Logs pages from it and hand-edits desync the two. `--details` formatting (numbered/bulleted/labeled lines, never a paragraph) is the logging caller's responsibility — `monitor_lib.format_list_block()` only decodes the literal `\n`-per-point convention it's given, it does not invent structure.
- **Logs and Reports are paginated, statically.** `monitor_lib.PAGE_SIZE` (10) entries/reports per page; page 1 is `index.html`, page N>1 is `page-N.html`, navigated with plain `<a>` Prev/Next links (`mlib.pagination_nav()`) — no JS, no server. Stale trailing page files are pruned automatically when a clean-logs/clean-reports shrinks the total below the previous page count.
- **Logs are the context-recovery mechanism, not just an audit trail.** The agent logs after every state-changing operation, small ones included, and for any real decision fills `--details` with labeled `DECISION:`/`WHY:`/`ARCHITECTURE:`/`NEXT:`/`GAPS:`/`ASSUMPTIONS:` fields (mechanical edits get a plain summary, no padding) — so a different agent with zero session context can read the log and resume work. See "Context capture" in `SKILL.md`.
- **Reports are immutable snapshots.** Authored by the agent from `reports/template.html` into `reports/<date>-<slug>.html`. No manifest file — `render_report.py`'s `scan_reports()` rebuilds `reports/index.html` and the top-level Dashboard by scanning `reports/*.html` directly and reading each report's own `<h1>`/Branch chip/Summary out of the file. An old report is never rewritten when the template changes — only new reports pick up new sections/KPIs. Reports include a **Decisions & Rationale** and a **Gaps & Assumptions** section pulled from the branch's log entries, and are generated by default before merging a branch with unreported changes.
- **The logging/reporting policy is mirrored into memory.** `/monitor:init` and `/monitor:update` save it as compressed `feedback`-type memory (when a persistent memory system is available to the installing agent) so later sessions apply it without re-reading `SKILL.md` in full; the target project's `CLAUDE.md` and `AGENTS.md` (both, whichever exist/are created) get the same policy as a durable fallback.
- **Branch-aware.** `monitor_lib.git_branch()` shells out to `git rev-parse --abbrev-ref HEAD`; returns `""` outside a repo (rendered as "no branch") or `detached@<sha>` on detached HEAD. Every page shows the *current* branch in the masthead; every log entry/report records the branch its *change* was made on — these can legitimately differ.
- **Shared page chrome lives in `monitor_lib.py`**: `PALETTE_CSS` (single source of truth for styling — sharp corners, dual light/dark theme via `prefers-color-scheme`, tabular numerals), `page()` (page shell), `branch_chip()`, `tabnav()`. All generated HTML is self-contained (no external assets, no `<script>` in reports).
- **Companion skills are optional and degrade gracefully**: `ui-ux-pro-max` (the UI is fixed via `mlib.PALETTE_CSS`, identical across every project), `superpowers` (verification gate on reports → falls back to marking reports *unverified*), `graphify` (orientation/find related code → falls back to grep), `openwiki` (doc sync → skipped, noted in follow-ups), `find-skills`, `copywriting` (report prose → written plainly). The engine itself never requires any of them.

## Editing the engine

- Any change to the additive-reconcile guarantee in `profile.py` must preserve backward compatibility — never repurpose or remove a `since`-versioned field. The log schema lives in `logger.py` (`REQUIRED`/`LEVELS`/`STATUSES`) — keep it fixed in code, identical across every project.
- Changes to `PALETTE_CSS` / `page()` in `monitor_lib.py` affect every generated page (Dashboard, Reports, Logs, and the report template) — check all three render scripts after editing shared chrome.
- After changing `plugins/monitor/skills/monitor/`, bump `version` in `plugins/monitor/.claude-plugin/plugin.json` so installed marketplaces pick up the update via `/plugin marketplace update monitor-tools`.
- `install-monitor.sh` and the plugin path must stay in sync: both ultimately expose `/monitor:init|log|report|record|search|update|clean-logs|clean-reports` — the plugin path via `$CLAUDE_PLUGIN_ROOT` + plugin namespace, the manual-copy path via commands nested under `.claude/commands/monitor/`.
- Never commit a generated per-project `monitor/` data folder (profile.json, logs, reports) from **this repo** — it's project-local generated content, not portable engine code, and this repo already ships the plugin source under `plugins/monitor/`. This is a repo-specific carve-out for `monitor-tools` dogfooding itself; it does **not** apply to a consumer project. In every other installed project, `monitor/` is committed by default — logs and reports are how a future agent (or teammate) recovers context, which only works if they're actually in the repo.
- **Never record development history, version changelogs, reasoning leakage, or design history inside skill definitions, READMEs, or any other user-facing documentation shipped to consumer projects** (`SKILL.md`, `commands/*.md`, `README.md`, `monitor/usage.md` templates, generated `CLAUDE.md`/`AGENTS.md` blocks). No "version 1 did X, this was later removed because...", no narration of what changed between plugin versions, no meta-commentary about why an approach was tried and abandoned. These files must read as clean, state-only documentation of *current* behavior — a first-time reader should never be able to tell the plugin has ever had a prior version. Version history belongs in git commits and `plugin.json`'s version field only. This rule itself must be propagated into every consumer project's `CLAUDE.md`/`AGENTS.md` by `/monitor:init` and `/monitor:update` (see the `monitor:start`/`monitor:end` block below and in `commands/init.md`/`update.md`).

## Testing changes locally

There's no test suite. To validate a change to the engine, run it against a scratch project:
```
./install-monitor.sh /path/to/scratch-project
# then, inside a Claude Code session opened on that project:
/monitor:init
/monitor:record   # or /monitor:log, /monitor:report individually
```
Engine scripts can also be invoked directly for quick checks: `python3 monitor/scripts/<script>.py --project-root <repo> --help`.

<!-- monitor:start -->
## monitor — operations log + reports (dogfooded on this repo)

This repo has **monitor** installed on itself via `./install-monitor.sh .`
(engine + commands under `.claude/`, generated data under the top-level
`monitor/`) — the same workflow this repo ships to consumers, used here to
develop the plugin itself. `monitor/` is generated local state, gitignored
(see `.gitignore`), never committed from this repo — same rule as any
consumer project's data folder, stated above under "Editing the engine."
Rules for using it live in `.claude/skills/monitor/SKILL.md` — read it
before running any command below.

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
- Never record development history, version changelogs, or reasoning
  leakage in any user-facing documentation (READMEs, skill files, this
  file, generated docs) — see "Editing the engine" above.
<!-- monitor:end -->
