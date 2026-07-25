---
description: Log an operation to the monitor operations log.
---

Append one operation entry to the monitor log for: **$ARGUMENTS**

**PRECONDITION — monitor must be initialised (check this FIRST).**
Verify `monitor/profile.json` exists (`test -f monitor/profile.json`). If it does
**not** exist, do **not** run any engine script or take any action. Reply with
exactly —

> ⚠️ monitor isn't initialised for this project yet. Run `/monitor:init` first, then re-run this command.

— and then STOP (end your turn immediately). Do not continue past this gate.

Read the **monitor** skill (`SKILL.md`) and `monitor/usage.md` first. Then log the
operation via the engine (never hand-edit the log):

```
python3 monitor/scripts/logger.py --operation <kebab-name> --tool <Tools> \
  --summary "<one line>" --status success|partial|failure --details "<verbose>" \
  [--files <paths>] [--task "<task>"] [--set <key=value> …]
```

The schema is locked in code (required fields, `level`/`status` enums) — not
profile-driven. Extra fields go in via `--set`. Structure `--details` yourself
(labeled lines / numbered / bulleted, joined by literal `\n`) — it's stored
and rendered as given, never auto-reformatted, so a freehand paragraph stays a
paragraph. The **branch** is recorded automatically (detected at log time) —
pass `--branch <name>` only to override it. `logger.py` itself refreshes the
Logs page and the Dashboard's KPIs after every call — do **not** separately
run `render_logs.py` or `render_report.py` after logging, it's redundant.
Relay to the user what was logged.
