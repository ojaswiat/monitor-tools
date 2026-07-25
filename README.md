<div align="center">

# Monitor

**A portable logging + reporting workflow for Claude Code — a session-to-session memory for agentic work that git was never built to hold.**

[![Version](https://img.shields.io/badge/version-1.9.0-blue)](plugins/monitor/.claude-plugin/plugin.json)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/)
[![Dependencies](https://img.shields.io/badge/dependencies-none-brightgreen)](#why-monitor)
[![License: MIT](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

</div>

Monitor gives any project a local `monitor/` folder — a **Dashboard** linking a **Reports** page (one self-contained HTML report per task or change) and a **Logs** page (a canonical, append-only text log rendered to filterable, paginated HTML). It's a Claude Code plugin, but the engine underneath is plain Python 3 stdlib with zero dependencies — no `pip install`, no CDN assets, no server.

## Monitor and git

Git already does what it does well: timestamped, immutable, chained history of every commit that made the cut. Monitor doesn't replace that, and doesn't try to be a second source of truth for what shipped — git stays authoritative there.

What git can't hold is everything that happened *before* something became a commit worth keeping: the approach that was tried and abandoned, the decision and the alternative it beat, a failed run logged honestly with `status=failure`. None of that reaches `git add`, and a squash-merge erases whatever per-commit reasoning did make it in. Monitor's log is append-only specifically so that record survives past the squash.

> [!NOTE]
> Monitor doesn't replace git. It records the part git structurally can't: everything that happened on the way to what you kept.

## Why monitor

- **Session-to-session context recovery.** Every log entry and report can capture the decision made, why (alternatives considered and rejected), what changed architecturally, what's next, and what gaps remain — so a different agent, or you a week later, can read the log and resume cold.
- **Logs by default, reports before merge.** The agent logs after every state-changing operation — including small ones — with no prompting needed, and generates a report by default before merging a branch with unreported changes.
- **Zero dependencies.** Pure Python 3 stdlib. The engine resolves its own root wherever it's copied — no hardcoded paths.
- **Backward-compatible by construction.** `monitor/profile.json` reconciles additively — only ever adds fields, never removes or renames. The log schema is locked in code and never migrated; a breaking change there is a new engine version, not a silent one.
- **Branch-aware.** Every page shows the current git branch; every log entry and report records the branch its change was made on.
- **Self-documenting install.** `/monitor:init` writes the logging/reporting policy into the target project's `CLAUDE.md` and `AGENTS.md` (creating whichever is missing), and mirrors it into memory when a persistent memory system is available.
- **Graceful degradation.** Optional companion skills (`ui-ux-pro-max`, `superpowers`, `graphify`, `openwiki`, `find-skills`, `copywriting`) are used when present, skipped cleanly when absent.

> [!NOTE]
> Monitor has exactly two jobs: **log** and **report**. It never detects a project's language, guesses build/test commands, or otherwise inspects what a project does — that's guessing, not recording. If an agent needs real project orientation, that's what a companion skill like `graphify` is for.

## Install

### A) As a Claude Code plugin (recommended, updatable)

```
/plugin marketplace add /absolute/path/to/monitor-marketplace
/plugin install monitor@monitor-tools
```

The path can be a local directory, or a git repo URL once this marketplace is pushed (`/plugin marketplace add owner/repo`). Update later with `/plugin marketplace update monitor-tools`.

### B) Without a marketplace (plain copy)

```
./install-monitor.sh /path/to/your/other-project
```

Copies `skills/monitor/` and nests the commands under `.claude/commands/monitor/`, so they invoke as `/monitor:*` without a plugin prefix. Re-run with `--force` to overwrite the engine + commands — your project's `monitor/` data folder is never touched.

## Quickstart

In the target project, run once:

```
/monitor:init
```

This seeds `monitor/profile.json` (just the project's directory name), copies the engine into `monitor/scripts/`, generates the Dashboard/Reports/Logs pages, and writes the policy into `CLAUDE.md`/`AGENTS.md`. Every other command refuses to run until `monitor/profile.json` exists.

From then on:

```
/monitor:record   # log the operation, and report it if code changed — the common case
/monitor:log      # log only
/monitor:report   # report only
```

## Commands

| Command | Does |
|---|---|
| `/monitor:init` | First-time setup (idempotent). Run once per project. |
| `/monitor:log` | Append one operation entry to the log. |
| `/monitor:report` | Author one HTML report and rebuild the Reports index. |
| `/monitor:record` | Log an operation and, if code changed, write a report — in one step. |
| `/monitor:search <query>` | Search the operations log by keyword; plain-text output. |
| `/monitor:update` | Additively reconcile the profile and regenerate the template/indexes. |
| `/monitor:clean-logs <N>` | Delete the oldest N log entries; re-render Logs. |
| `/monitor:clean-reports <N>` | Delete the oldest N reports; re-render Reports + Dashboard. |

## What you get

A project-local `monitor/` folder, generated by `/monitor:init` and owned by the target project — not this repo:

- **Dashboard** (`monitor/index.html`) — links Reports and Logs, shows the current branch.
- **Logs** (`monitor/logs/`) — a canonical, newest-first `operations.mtr` (schema locked in code), rendered to paginated, filterable HTML. Never hand-edited — always written through `logger.py`.
- **Reports** (`monitor/reports/`) — one self-contained HTML file per task or change, authored from `template.html`. No manifest file: the index is scanned fresh from `reports/*.html`, reading each report's own title/branch/summary out of it. Immutable once written: a template upgrade never rewrites old reports.

## How it works

- **Init-gated.** Every command except `/monitor:init` fails fast (exit 2) until `monitor/profile.json` exists.
- **Context capture.** For real decisions, `--details` carries labeled `DECISION:` / `WHY:` / `ARCHITECTURE:` / `NEXT:` / `GAPS:` / `ASSUMPTIONS:` fields; mechanical edits just get a plain summary. Reports pull a **Decisions & Rationale** and a **Gaps & Assumptions** section straight from those fields.
- **Branch tracking.** `git rev-parse --abbrev-ref HEAD` at render/log time; degrades to `no branch` outside a repo and `detached@<sha>` on detached HEAD.
- **Immutable reports.** Old report HTML is never rewritten when the template upgrades — only new reports pick up new sections or KPIs.

> [!TIP]
> Reports are for code changes only — a docs-only tweak or a discussion gets logged, not reported.

<details>
<summary>Companion skills (all optional)</summary>

| Skill | Role | Fallback if absent |
|---|---|---|
| `ui-ux-pro-max` | UI is fixed and identical across every project | n/a |
| `superpowers` | Gates reports on real build/test verification | Render but mark **unverified** |
| `graphify` | Orientation — find related code | grep / raw reads |
| `openwiki` | Doc sync after commits | Skip; note in follow-ups |
| `find-skills` | Improves skill discovery at init | Recommend from this table |
| `copywriting` | Polishes report prose | Write plainly |

</details>

<details>
<summary>Repo layout</summary>

```
monitor-marketplace/
  .claude-plugin/marketplace.json     the catalog (one plugin: monitor)
  plugins/monitor/                    the plugin
    .claude-plugin/plugin.json        manifest (name, version, author)
    skills/monitor/                   SKILL.md + engine scripts + base template
    commands/                         flat *.md → /monitor:init|log|report|record|update|clean-*
    README.md
  install-monitor.sh                  no-marketplace fallback installer
  README.md                           (this file)
```

</details>

## Notes

- **Don't copy another project's top-level `monitor/` data folder.** It's per-project generated content (its reports, logs, profile). `/monitor:init` creates a fresh one — only the `.claude/skills/monitor` engine and `.claude/commands` are portable.
- **The engine finds itself in both install modes.** Commands resolve it via `$CLAUDE_PLUGIN_ROOT` when installed as a plugin, and fall back to `.claude/skills/monitor` when copied manually.
- **Nothing beyond Python 3 is required.** Companion skills are pure enhancement.
