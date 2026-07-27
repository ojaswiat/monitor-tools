---
description: Search the monitor operations log for entries matching a query.
---

Search the monitor log for: **$ARGUMENTS**

**PRECONDITION — monitor must be initialised (check this FIRST).**
Verify `monitor/profile.json` exists (`test -f monitor/profile.json`). If it does
**not** exist, do **not** run any engine script or take any action. Reply with
exactly —

> ⚠️ monitor isn't initialised for this project yet. Run `/monitor:init` first, then re-run this command.

— and then STOP (end your turn immediately). Do not continue past this gate.

Read the **monitor** skill (`SKILL.md`) first. Then search via the engine:

```
python3 monitor/scripts/search.py --project-root . --query "<text>" \
    [--scope logs|reports|tasks|all] \
    [--branch <name>] [--status success|partial|failure] [--level LEVEL] [--limit N]
```

If `$ARGUMENTS` isn't a clean query string (e.g. it's empty), ask the user
for one directly instead of guessing. Output is plain text, one block per
match, in the same shape as a log entry — read it directly. There is no HTML
results page: a search result is different every time it's run, while every
other monitor page is static and pre-built, so generating one here would be
both extra work and immediately stale. Relay the matches (or "no matches
found") to the user in your own words rather than dumping the raw output
verbatim. `--scope` defaults to `all` (every source); narrow to
`logs`/`reports`/`tasks` to search just one. `--branch`/`--status`/`--level`
only apply when the effective scope includes logs.
