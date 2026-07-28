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
   `monitor/reports/<YYYY-MM-DD>-<slug>.html`. The template's design is fixed
   (`mlib.PALETTE_CSS`, identical across every project) — only fill in content.
   Fill every `{{ branch }}` placeholder with the
   branch the work was done on (`git rev-parse --abbrev-ref HEAD`). Fill
   `{{ commit }}` with the range of commits this report covers, as
   `<first-short-sha>..<last-short-sha>` (e.g. `58e342a..bd3ecb7`) — the
   first commit unique to this branch's work through the current `HEAD` (e.g.
   `git log --oneline <base-branch>..HEAD`); if the report covers exactly one
   commit, use just that single short sha with no range.
   Fill `{{ date }}` yourself with today's date (`YYYY-MM-DD`) — this is the
   "Generated" chip and no script ever substitutes it; an unfilled
   `{{ date }}` ships verbatim into the published report.
   Fill `{{ date_created }}` yourself as well, with the date the underlying
   work began (your own judgment — often earlier than `{{ date }}`).
   Leave `{{ last_modified }}` alone — that is the only date placeholder that
   is stamped automatically: `render_report.py --lock-report` fills it in at
   the end of authoring. **Only the
   text content changes** — a request about tone, audience, reading level, or
   language (e.g. "explain it like I'm 11") changes the words in each section,
   never the `<style>` block, palette, layout, or class names. The design is
   locked regardless of what the content-side request asks for.
3. **Lock the design** — force-correct the file back onto the canonical
   palette in case authoring drifted, before it's indexed:
   `python3 monitor/scripts/render_report.py --lock-report reports/<file>.html`.
4. Run `python3 monitor/scripts/render_report.py` to rebuild the Reports
   index + Dashboard. There is no manifest to update — the new report is
   picked up automatically by scanning `reports/*.html` and reading its own
   `<h1>`/Branch chip/Summary straight out of the file.
5. Relay the report path to the user.
