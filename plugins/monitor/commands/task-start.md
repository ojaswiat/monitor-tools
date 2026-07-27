---
description: Start a new lifecycle-tracked task.
---

Start a monitor task for: **$ARGUMENTS**

**PRECONDITION — monitor must be initialised (check this FIRST).**
Verify `monitor/profile.json` exists (`test -f monitor/profile.json`). If it does
**not** exist, do **not** run any engine script or take any action. Reply with
exactly —

> ⚠️ monitor isn't initialised for this project yet. Run `/monitor:init` first, then re-run this command.

— and then STOP (end your turn immediately). Do not continue past this gate.

Read the **monitor** skill (`SKILL.md`) and `monitor/usage.md` first,
specifically the "Tasks" section. Then start the task via the engine:

```
python3 monitor/scripts/tasks.py --project-root . start --title "<short title>" \
    [--status open] [--summary "..."] [--tokens N] [--credits N] [--cost N] \
    [--skills-used a b] [--tools-called a b] [--details "..."]
```

The command prints the generated `task_id` (an 8-character id) — **relay it
to the user prominently and remember it for this session**: every
`/monitor:task-update` and `/monitor:task-close` call for this task needs it,
and log entries made while working on it can carry it via `logger.py
--task-id <id>` to cross-reference. Status defaults to `open`; use `--status
in_progress` if work starts immediately.
