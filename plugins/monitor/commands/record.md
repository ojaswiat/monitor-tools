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
     [--files <paths>] [--task-id <id>] [--set <key=value> …]
   ```
   The schema is locked in code — extra fields go in via
   `--set`. Structure `--details` yourself (labeled lines / numbered /
   bulleted, joined by literal `\n`) — it's stored and rendered as given. The
   **branch** is recorded automatically — pass `--branch <name>` only to
   override it. `logger.py` itself refreshes the Logs page and the
   Dashboard's KPIs after every call — don't separately run `render_logs.py`
   here, it's redundant.
2. **Report** — only if code changed or the user explicitly asked. Gate on
   `superpowers:verification-before-completion` if available (else mark the report
   status **unverified**). Author it from `monitor/reports/template.html` into
   `monitor/reports/<YYYY-MM-DD>-<slug>.html`. The template's design is fixed
   (`mlib.PALETTE_CSS`, identical across every project) — only fill in content.
   Fill every `{{ branch }}` placeholder with the
   branch the work was done on, and `{{ commit }}` with the range of commits
   this report covers as `<first-short-sha>..<last-short-sha>` (or a single
   short sha if the report covers exactly one commit).
   Fill `{{ date }}` yourself with today's date (`YYYY-MM-DD`) — this is the
   "Generated" chip and no script ever substitutes it; an unfilled
   `{{ date }}` ships verbatim into the published report.
   Fill `{{ date_created }}` yourself as well, with the date the underlying
   work began (your own judgment — often earlier than `{{ date }}`).
   Leave `{{ last_modified }}` alone — that is the only date placeholder that
   is stamped automatically: `render_report.py --lock-report` fills it in at
   the end of authoring. **Only the text content changes** — a request
   about tone, audience, reading level, or language changes the words in each
   section, never the `<style>` block, palette, layout, or class names. Then
   lock the design: `python3 monitor/scripts/render_report.py --lock-report
   reports/<file>.html` (force-corrects the file back onto the canonical
   palette before it's indexed). There is no manifest to update — just run
   `python3 monitor/scripts/render_report.py` to rebuild the Reports index +
   Dashboard.
3. Relay what was logged and whether a report was written (with its path).
