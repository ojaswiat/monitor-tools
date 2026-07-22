# monitor (plugin)

A portable logging + reporting workflow for Claude Code projects. Adds a project-local `monitor/` folder — a **Dashboard** linking a **Reports** page (self-contained HTML report per task/change) and a **Logs** page (rendered from a canonical newest-first `operations.mtr`). The report template is seeded per project from `monitor/profile.json` and evolves **additively** (backward compatible); the log schema itself is locked in code, identical across every project.

## Components
- **Skill:** `skills/monitor/SKILL.md` + `skills/monitor/scripts/` (engine: `monitor_lib`, `profile`, `logger`, `render_logs`, `render_report`, `clean` — all Python 3 stdlib) + `skills/monitor/assets/base_template.html` (fallback template).
- **Commands:** `/monitor:init`, `/monitor:log`, `/monitor:report`, `/monitor:record`, `/monitor:update`, `/monitor:clean-logs <N>`, `/monitor:clean-reports <N>`.

## Design guarantees
- **stdlib-only, zero deps, no hardcoded project paths** — each script resolves its own project root.
- **Branch-aware:** every page shows the current branch (masthead chip + KPI), and each log entry / report records the branch its change was made on. Detected automatically; degrades to `no branch` outside a git repo.
- **Init-gated:** every command except `/monitor:init` fails fast (exit 2) until `monitor/profile.json` exists.
- **Immutable reports:** old report HTML is never rewritten on a template upgrade.
- **Context-recoverable:** log entries and reports capture the decision, the reasoning behind it, the architecture/design touched, what's left to do, and known gaps — enough for a new agent with zero prior context to read the log/report and continue the work immediately.
- **Graceful degradation** across optional companion skills (`ui-ux-pro-max`, `superpowers`, `graphify`, `openwiki`, `find-skills`, `copywriting`).

## Usage
Run `/monitor:init` once per project — it also saves the logging/reporting policy to memory so it applies automatically in later sessions without re-reading `SKILL.md`. Then run `/monitor:record` after operations (or `/monitor:log` and `/monitor:report` on their own). See the marketplace `README.md` for install instructions.
