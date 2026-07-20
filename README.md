# monitor-tools — a Claude Code plugin marketplace

Distributes the **`monitor`** plugin: a portable logging + reporting workflow that
gives any project a local `monitor/` folder (a **Dashboard** with **Reports** and
**Logs** pages), driven by a project-specific log schema and report template that
evolve additively. The engine is **stdlib-only Python 3** — no pip installs, no
external assets, no hardcoded paths.

## What's in here
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

## Install — two ways

### A) As a Claude Code plugin (recommended, updatable)
From a Claude Code session, add this marketplace and install the plugin:
```
/plugin marketplace add /absolute/path/to/monitor-marketplace
/plugin install monitor@monitor-tools
```
- The path can be a local directory (as above) **or** a git repo URL once you push
  this marketplace to GitHub/GitLab (`/plugin marketplace add owner/repo`).
- Update later with `/plugin marketplace update monitor-tools` (bump the plugin
  `version` in `plugin.json` on each release so users pull updates).

### B) Without a marketplace (plain copy)
Run the fallback installer against any project directory:
```
./install-monitor.sh /path/to/your/other-project
```
It copies `skills/monitor/` and nests the commands under `.claude/commands/monitor/`
(so they invoke as `/monitor:*` without a plugin prefix). Re-run with `--force` to
overwrite the engine + commands.

## After installing — REQUIRED first step
In the target project, run:
```
/monitor:init
```
This detects the project, seeds `monitor/profile.json`, copies the engine into
`monitor/scripts/`, and generates the Dashboard, Reports, and Logs pages. **Every
other command refuses to run until `monitor/profile.json` exists.**

## Important notes
- **Don't copy another project's top-level `monitor/` data folder.** That folder is
  per-project generated content (its reports, logs, profile). `/monitor:init`
  creates a fresh one. Only the `.claude/skills/monitor` engine + `.claude/commands`
  are portable.
- **The engine finds itself in both install modes.** The commands resolve the engine
  via `$CLAUDE_PLUGIN_ROOT` when installed as a plugin, and fall back to
  `.claude/skills/monitor` when copied manually — so `/monitor:init` works either way.
- **Companion skills are optional.** `monitor` uses `ui-ux-pro-max`, `superpowers`,
  `graphify`, `openwiki`, `find-skills`, and `copywriting` when present, and degrades
  gracefully (base template, reports marked *unverified*, `git diff` for files-touched,
  etc.) when they are absent. Nothing is required beyond Python 3.

## Commands
| Command | Does |
|---|---|
| `/monitor:init` | First-time setup (idempotent). |
| `/monitor:log` | Append one operation entry to the log. |
| `/monitor:report` | Author one HTML report and rebuild the Reports index. |
| `/monitor:record` | Log an operation and, if code changed, write a report — in one step. |
| `/monitor:update` | Additively reconcile profile + regenerate schema/template/indexes. |
| `/monitor:clean-logs <N>` | Delete the newest N log entries; re-render Logs. |
| `/monitor:clean-reports <N>` | Delete the newest N reports; re-render Reports + Dashboard. |
