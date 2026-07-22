---
description: Delete the most recent N log entries and re-render the Logs page.
---

Delete the newest **$ARGUMENTS** log entries via the monitor engine.

**PRECONDITION — monitor must be initialised (check this FIRST).**
Verify `monitor/profile.json` exists (`test -f monitor/profile.json`). If it does
**not** exist, do **not** run any engine script or delete anything. Reply with
exactly —

> ⚠️ monitor isn't initialised for this project yet. Run `/monitor:init` first, then re-run this command.

— and then STOP (end your turn immediately).

1. Parse N from `$ARGUMENTS` (a positive integer). If missing/invalid, ask the
   user for N and stop.
2. Preview first: `python3 monitor/scripts/clean.py --project-root . --logs <N> --dry-run`
   and show the user how many of how many entries will be removed.
3. On confirmation, run without `--dry-run`:
   `python3 monitor/scripts/clean.py --project-root . --logs <N>`
   (deletes the newest N rows from `log.db` and re-renders the Logs page).
4. Report the new entry count.
