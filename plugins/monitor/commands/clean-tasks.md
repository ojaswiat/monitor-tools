---
description: Delete the oldest N tasks (all their events) and re-render the Tasks page + Dashboard.
---

Delete the oldest **$ARGUMENTS** tasks via the monitor engine.

**PRECONDITION — monitor must be initialised (check this FIRST).**
Verify `monitor/profile.json` exists (`test -f monitor/profile.json`). If it does
**not** exist, do **not** run any engine script or delete anything. Reply with
exactly —

> ⚠️ monitor isn't initialised for this project yet. Run `/monitor:init` first, then re-run this command.

— and then STOP (end your turn immediately).

1. Parse N from `$ARGUMENTS` (a positive integer). If missing/invalid, ask the
   user for N and stop.
2. Preview first: `python3 monitor/scripts/clean.py --project-root . --tasks <N> --dry-run`
   and show the user how many of how many tasks (and all their events) will be removed.
3. On confirmation, run without `--dry-run`:
   `python3 monitor/scripts/clean.py --project-root . --tasks <N>`
   (removes the oldest N tasks — every task-start/task-update/task-close
   event for each — from `tasks.mtr` and re-renders the Tasks page +
   Dashboard, whose Open-tasks KPI is recounted from what's left).
4. Report the new task count.
