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
   `python3 monitor/scripts/render_report.py` (also rebuilds `tasks/index.html`)
   and `python3 monitor/scripts/render_logs.py`.
   Existing report HTML files are immutable snapshots — they are not touched;
   `operations.mtr` is preserved and re-rendered tolerant of older entries.
4. Refresh `monitor/usage.md` from the current companion-skill availability.
   The template's design is fixed (`mlib.PALETTE_CSS`, identical across every
   project) — regeneration only adds new KPIs/sections from the profile, never
   a custom palette or layout.
5. Refresh the `<!-- monitor:start -->` / `<!-- monitor:end -->` block in
   **both** `CLAUDE.md` and `AGENTS.md` (same content as `/monitor:init` step
   8), independently per file — replace the block in place if present, append
   it if a file exists without one, or skip that file silently if it was
   deleted (don't recreate a deleted file here; that's init's job, not
   update's).
6. **Ensure the pending-state hooks are installed.** If the project's
   `.claude/settings.json` doesn't yet have the `PostToolUse`/
   `UserPromptSubmit` entries pointing at `pending.py` (same JSON shown in
   `/monitor:init` step 7), add them now — additive merge, same as init.
   Already-initialized projects that predate this feature pick it up here.
7. If a persistent memory system is available and already holds the monitor
   logging/reporting policy from a prior `/monitor:init`, refresh those
   entries in place (same content as `/monitor:init` step 9) rather than
   duplicating them. If none exist yet, save them now. If no memory system is
   available, skip silently.
8. Report the profile diff and which assets were regenerated.
