---
description: Write an HTML report for a completed task or change.
---

Author a monitor report for: **$ARGUMENTS**

**PRECONDITION — monitor must be initialised (check this FIRST).**
Verify `monitor/profile.json` exists (`test -f monitor/profile.json`). If it does
**not** exist, do **not** run any engine script or take any action. Reply with
exactly —

> ⚠️ monitor isn't initialised for this project yet. Run `/monitor:init` first, then re-run this command.

— and then STOP (end your turn immediately). Do not continue past this gate.

Read the **monitor** skill (`SKILL.md`) and `monitor/usage.md` first. Then:

1. Gate on `superpowers:verification-before-completion` if available (else mark
   the report status **unverified**).
2. Author the report from `monitor/reports/template.html` into
   `monitor/reports/<YYYY-MM-DD>-<slug>.html` (use `ui-ux-pro-max` to (re)design
   the template if available). Fill every `{{ branch }}` placeholder with the
   branch the work was done on (`git rev-parse --abbrev-ref HEAD`). **Only the
   text content changes** — a request about tone, audience, reading level, or
   language (e.g. "explain it like I'm 11") changes the words in each section,
   never the `<style>` block, palette, layout, or class names. The design is
   locked regardless of what the content-side request asks for.
3. **Lock the design** — force-correct the file back onto the canonical
   palette in case authoring drifted, before it's indexed:
   `python3 monitor/scripts/render_report.py --lock-report reports/<file>.html`.
4. **Prepend** `{date,file,title,description,branch}` to
   `monitor/reports/manifest.json` (newest-first — insert at index 0), then run
   `python3 monitor/scripts/render_report.py` to rebuild the Reports index +
   Dashboard.
5. Relay the report path to the user.
