---
description: Log an operation and, if code changed, write a report — in one step.
---

Record the operation for: **$ARGUMENTS** — log it, then write a report if code
changed.

**PRECONDITION — monitor must be initialised (check this FIRST).**
Verify `monitor/profile.json` exists (`test -f monitor/profile.json`). If it does
**not** exist, do **not** run any engine script or take any action. Reply with
exactly —

> ⚠️ monitor isn't initialised for this project yet. Run `/monitor:init` first, then re-run this command.

— and then STOP (end your turn immediately). Do not continue past this gate.

Read the **monitor** skill (`SKILL.md`) and `monitor/usage.md` first. Then:

1. **Log** the operation via the engine (never hand-edit the log):
   ```
   python3 monitor/scripts/logger.py --operation <kebab-name> --tool <Tools> \
     --summary "<one line>" --status success|partial|failure --details "<verbose>" \
     [--files <paths>] [--task "<task>"] [--set <key=value> …]
   ```
   Validate mentally against `monitor/logs/schema.json`; include profile-specific
   fields via `--set`. The **branch** is recorded automatically — pass
   `--branch <name>` only to override it.
2. **Report** — only if code changed or the user explicitly asked. Gate on
   `superpowers:verification-before-completion` if available (else mark the report
   status **unverified**). Author it from `monitor/reports/template.html` into
   `monitor/reports/<YYYY-MM-DD>-<slug>.html`. The template's design is fixed
   (`mlib.PALETTE_CSS`, identical across every project) — only fill in content.
   Fill every `{{ branch }}` placeholder with the
   branch the work was done on. **Only the text content changes** — a request
   about tone, audience, reading level, or language changes the words in each
   section, never the `<style>` block, palette, layout, or class names. Then
   lock the design: `python3 monitor/scripts/render_report.py --lock-report
   reports/<file>.html` (force-corrects the file back onto the canonical
   palette before it's indexed). **Prepend** `{date,file,title,description,branch}`
   to `monitor/reports/manifest.json` (index 0), then run
   `python3 monitor/scripts/render_report.py` to rebuild the Reports index +
   Dashboard.
3. Relay what was logged and whether a report was written (with its path).
