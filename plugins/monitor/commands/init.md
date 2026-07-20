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
7. Add a one-line pointer to the project `CLAUDE.md`: monitoring/logging/reporting
   rules live in the **monitor** skill (`SKILL.md`).

Report the created tree and the detected profile summary.
