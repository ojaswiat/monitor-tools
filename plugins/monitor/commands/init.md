---
description: Initialise the monitor plugin for this project (idempotent).
---

Initialise **monitor** for this project. Read the **monitor** skill (`SKILL.md`) first.

1. If `monitor/profile.json` already exists, switch to verify/repair mode: report
   what is present and only create what is missing (do not clobber data).
2. **Seed the profile and copy the engine** into the project so it is
   self-contained. Run these as ONE block so `$ENGINE` (which locates the engine
   whether monitor is installed as a plugin or copied into `.claude/skills/`)
   stays set:
   ```bash
   ENGINE="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/monitor}"; [ -z "$ENGINE" ] && ENGINE=".claude/skills/monitor"
   python3 "$ENGINE/scripts/profile.py" --project-root .
   mkdir -p monitor/scripts && cp "$ENGINE"/scripts/*.py monitor/scripts/
   ```
   (`profile.py` detects language, build/test commands, VCS.)
4. Generate project-specific assets from the profile:
   `python3 monitor/scripts/render_report.py` (writes `logs/schema.json`,
   `reports/template.html`, `reports/index.html`, `index.html`, seeds
   `reports/manifest.json`) and `python3 monitor/scripts/render_logs.py`
   (creates an empty-state Logs page if there is no log yet).
5. Probe companion skills (graphify, superpowers, openwiki, ui-ux-pro-max,
   find-skills, copywriting) via `.claude/settings.json` enabledPlugins and the
   skills folder. Write `monitor/usage.md`: for each, PRESENT/ABSENT and how
   monitor uses it here (from the SKILL.md companion table). For absent high-fit
   skills, recommend them with the enable command — installation stays
   user-gated (on approval, run only their init, e.g. `graphify update .`,
   `/openwiki:wiki init`).
6. Ensure `.gitignore` contains `monitor/scripts/__pycache__/`.
7. Add or update a **monitor** section in the project's `CLAUDE.md` (create the
   file if it does not exist). Write it between
   `<!-- monitor:start -->` / `<!-- monitor:end -->` markers so re-running
   `/monitor:init` or `/monitor:update` replaces the block instead of
   duplicating it. Content:
   ```markdown
   <!-- monitor:start -->
   ## monitor — operations log + reports

   This project has **monitor** installed: a local logging/reporting workflow.
   It keeps a project-local `monitor/` folder — a Dashboard linking a **Reports**
   page (one self-contained HTML report per task/change) and a **Logs** page
   (rendered from `monitor/logs/operations.log`). Rules for using it live in
   the skill at `SKILL.md` (or `$CLAUDE_PLUGIN_ROOT/skills/monitor/SKILL.md`
   when installed as a plugin) — read it before running any command below.

   **When to use it:**
   - After a state-changing operation (edit+build+commit can be one entry) —
     run `/monitor:log` or `/monitor:record` (log **and** report in one step).
   - After code changes specifically — write a report with `/monitor:report`
     (or via `/monitor:record`). Never report a discussion or doc-only tweak.
   - On failure, log it anyway with `status=failure` and the real error —
     don't skip logging just because the operation didn't succeed.

   **Commands:**
   | Command | Does |
   |---|---|
   | `/monitor:init` | First-time setup (idempotent). Run once per project. |
   | `/monitor:log` | Append one operation entry to the log. |
   | `/monitor:report` | Author one HTML report + rebuild the Reports index. |
   | `/monitor:record` | Log, and if code changed, report — in one step. |
   | `/monitor:update` | Re-detect + additively reconcile the profile, refresh assets. |
   | `/monitor:clean-logs <N>` | Delete the newest N log entries; re-render Logs. |
   | `/monitor:clean-reports <N>` | Delete the newest N reports; re-render Reports + Dashboard. |

   **Rules:**
   - Every command except `/monitor:init` requires `monitor/profile.json` to
     exist — it fails fast otherwise. Run init first if it's missing.
   - Never hand-edit `monitor/logs/operations.log` — always go through
     `logger.py` (via `/monitor:log` or `/monitor:record`); hand-edits desync
     the log from the rendered Logs page.
   - Reports are immutable snapshots — never rewrite an old report when the
     template changes; only new reports pick up new sections.
   - `monitor/profile.json` evolves additively only — `/monitor:update` adds
     detected fields, never removes or renames existing ones.
   <!-- monitor:end -->
   ```

Report the created tree and the detected profile summary.
