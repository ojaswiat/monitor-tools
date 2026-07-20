---
description: Delete the most recent N reports and re-render the Reports index + Dashboard.
---

Delete the newest **$ARGUMENTS** reports via the monitor engine.

**PRECONDITION — monitor must be initialised (check this FIRST).**
Verify `monitor/profile.json` exists (`test -f monitor/profile.json`). If it does
**not** exist, do **not** run any engine script or delete anything. Reply with
exactly —

> ⚠️ monitor isn't initialised for this project yet. Run `/monitor:init` first, then re-run this command.

— and then STOP (end your turn immediately).

1. Parse N from `$ARGUMENTS` (a positive integer). If missing/invalid, ask the
   user for N and stop.
2. Preview first: `python3 monitor/scripts/clean.py --project-root . --reports <N> --dry-run`
   and show the user the exact report files that will be deleted.
3. On confirmation, run without `--dry-run`:
   `python3 monitor/scripts/clean.py --project-root . --reports <N>`
   (deletes the newest N report files, removes them from `reports/manifest.json`,
   and re-renders the Reports index + Dashboard).
4. Report the new report count.
