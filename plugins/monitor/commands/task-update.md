---
description: Update a task's status and/or metrics mid-flight.
---

Update monitor task: **$ARGUMENTS**

**PRECONDITION — monitor must be initialised (check this FIRST).**
Verify `monitor/profile.json` exists (`test -f monitor/profile.json`). If it does
**not** exist, do **not** run any engine script or take any action. Reply with
exactly —

> ⚠️ monitor isn't initialised for this project yet. Run `/monitor:init` first, then re-run this command.

— and then STOP (end your turn immediately). Do not continue past this gate.

Read the **monitor** skill (`SKILL.md`) and `monitor/usage.md` first,
specifically the "Tasks" section. `$ARGUMENTS` should identify the task (by
its id, given when it was started) and what changed. Then update it via the engine:

```
python3 monitor/scripts/tasks.py --project-root . update --task-id <id> \
    --status open|in_progress|needs_approval|needs_retry|blocked \
    --summary "<what changed>" [--tokens N] [--credits N] [--cost N] \
    [--skills-used a b] [--tools-called a b] [--details "..."]
```

`--status` must be one of the **non-terminal** values above — use
`/monitor:task-close` for a final success/failed/cancelled outcome. Metrics
passed here are additive: they accumulate on top of whatever the task
already has, they don't replace the running total.
