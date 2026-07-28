---
description: Show the project's current status — open tasks, recent activity, pending items, and next steps — directly in chat.
---

Report project status.

**PRECONDITION — monitor must be initialised (check this FIRST).**
Verify `monitor/profile.json` exists (`test -f monitor/profile.json`). If it does
**not** exist, do **not** run any engine script or take any action. Reply with
exactly —

> ⚠️ monitor isn't initialised for this project yet. Run `/monitor:init` first, then re-run this command.

— and then STOP (end your turn immediately). Do not continue past this gate.

Read the **monitor** skill (`SKILL.md`) first. Then compute status via the engine:

```
python3 monitor/scripts/status.py --project-root . [--log-limit N] [--commit-limit N]
```

This prints one JSON object to stdout — nothing is written to disk, by design.
`/monitor:status` never creates a file; every fact in the JSON was extracted
mechanically (open tasks, the last `--log-limit` log entries, `NEXT:`/`GAPS:`/
`ASSUMPTIONS:` fields regex-extracted from those entries' `--details` text,
the pending-state gate's own data, and a bit of git history) — nothing in the
script is inferred or judged, so relay it faithfully rather than guessing at
information the JSON doesn't contain.

Read the JSON and answer **directly in chat**, organized as four short
sections — do not create a report, dashboard entry, or any other file for
this command:

1. **What Happened** — from `recent_logs`, a few concise bullets of the most
   recent operations (operation, status, summary).
2. **Currently Working On** — from `current_activity`: if `source` is
   `open_task`, say which task; if `last_log`, say the most recent operation;
   if `none`, say there's no open task or log activity yet.
3. **Pending & Queued** — from `pending` (unlogged commits, an unreported
   merge, an untracked-plan-file nudge) and any other entries in
   `open_tasks` beyond the one already covered above.
4. **Next Steps For You** — from `next_steps`, one bullet per `NEXT:`/`GAPS:`/
   `ASSUMPTIONS:` field found, labeled by which kind it is. If empty, say so
   plainly rather than inventing a step.

If a section has nothing to report (e.g. no pending state, no open tasks),
say so briefly rather than omitting the section silently — the point is a
complete snapshot, not just the parts with content.
