---
description: Update monitor's assets (profile, schema, template) using available skills.
---

Update **monitor** for this project. Read the **monitor** skill (`SKILL.md`) first.
This is a backward-compatible upgrade — additive only.

**PRECONDITION — monitor must be initialised (check this FIRST).**
Verify `monitor/profile.json` exists (`test -f monitor/profile.json`). If it does
**not** exist, do **not** run any engine script or take any action. Reply with
exactly —

> ⚠️ monitor isn't initialised for this project yet. Run `/monitor:init` first, then re-run this command.

— and then STOP (end your turn immediately).

1. Reconcile the profile (adds newly detected fields, never removes/renames,
   bumps `profileVersion`): `python3 monitor/scripts/profile.py --project-root .`
   — report the printed "added:" diff.
2. Re-copy the engine so the project has the latest scripts (resolve the engine
   location whether monitor is a plugin or copied into `.claude/skills/`):
   ```bash
   ENGINE="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/monitor}"; [ -z "$ENGINE" ] && ENGINE=".claude/skills/monitor"
   cp "$ENGINE"/scripts/*.py monitor/scripts/
   ```
3. Regenerate assets from the reconciled profile:
   `python3 monitor/scripts/render_report.py` and
   `python3 monitor/scripts/render_logs.py`.
   Existing report HTML files are immutable snapshots — they are not touched;
   `operations.log` is preserved and re-rendered tolerant of older entries.
4. Refresh `monitor/usage.md` from the current companion-skill availability. If
   `ui-ux-pro-max` is available, offer to re-design `reports/template.html`;
   apply only additively (new KPIs/sections), preserving existing structure.
5. Refresh the `<!-- monitor:start -->` / `<!-- monitor:end -->` block in the
   project's `CLAUDE.md` (same content as `/monitor:init` step 7) — replace the
   block in place if present, append it if the file exists without one, or
   skip silently if `CLAUDE.md` was deleted (don't recreate it here).
6. Report the profile diff and which assets were regenerated.
