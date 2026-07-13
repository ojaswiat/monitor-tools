---
description: Log the operation and (if code changed) write a report, from the user's prompt.
---

Run the **monitor** skill's combined log + report action for: **$ARGUMENTS**

**PRECONDITION — monitor must be initialised (check this FIRST).**
Verify `monitor/profile.json` exists (`test -f monitor/profile.json`). If it does
**not** exist, monitor is not initialised for this project: do **not** run any
engine script, log, report, or take any other action. Reply with exactly —

> ⚠️ monitor isn't initialised for this project yet. Run `/monitor:init` first, then re-run this command.

— and then STOP (end your turn immediately). Do not continue past this gate.

Read the **monitor** skill (`SKILL.md`) and `monitor/usage.md` first. Then:

1. **Log** the operation via the engine (never hand-edit the log):
   `python3 monitor/scripts/logger.py --operation <kebab-name> --tool <Tools>
   --summary "<one line>" --status success|partial|failure --details "<verbose>"
   [--files <paths>] [--task "<task>"] [--set <key=value> …]`
   Validate mentally against `monitor/logs/schema.json`; include profile-specific
   fields via `--set`.
3. **Report** — only if code changed or the user explicitly asked. Gate on
   `superpowers:verification-before-completion` if available (else mark the report
   status **unverified**). Author the report from `monitor/reports/template.html`
   into `monitor/reports/<YYYY-MM-DD>-<slug>.html` (base every report on the
   project's `monitor/reports/template.html`; use `ui-ux-pro-max` to (re)design it
   if available). **Prepend**
   `{date,file,title,description}` to `monitor/reports/manifest.json` (newest-first —
   insert at index 0), then run
   `python3 monitor/scripts/render_report.py` to rebuild the Reports index +
   Dashboard.
4. Relay to the user what was logged and whether a report was written (with its path).
