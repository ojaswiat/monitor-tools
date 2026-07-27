---
description: Close a task with its final outcome.
---

Close monitor task: **$ARGUMENTS**

**PRECONDITION — monitor must be initialised (check this FIRST).**
Verify `monitor/profile.json` exists (`test -f monitor/profile.json`). If it does
**not** exist, do **not** run any engine script or take any action. Reply with
exactly —

> ⚠️ monitor isn't initialised for this project yet. Run `/monitor:init` first, then re-run this command.

— and then STOP (end your turn immediately). Do not continue past this gate.

Read the **monitor** skill (`SKILL.md`) and `monitor/usage.md` first,
specifically the "Tasks" section. `$ARGUMENTS` should identify the task (by
its id) and its outcome.
Then close it via the engine:

```
python3 monitor/scripts/tasks.py --project-root . close --task-id <id> \
    --status success|failed|cancelled --summary "<final outcome>" \
    [--tokens N] [--credits N] [--cost N] [--skills-used a b] \
    [--tools-called a b] [--details "..."]
```

`--status` must be one of the **terminal** values above — use
`/monitor:task-update` for anything still in progress. Once closed, don't
issue further update/close calls for the same `task_id`; start a new task if
more work on the same topic comes up later.
