# Hard-rule logging/task-tracking in the injected CLAUDE.md/AGENTS.md block

## Problem

The `monitor:start`/`monitor:end` block that `/monitor:init` and
`/monitor:update` inject into a Guest project's `CLAUDE.md`/`AGENTS.md`
phrases logging, task-tracking, and reporting identically, as soft
defaults ("no need to ask first"). Discussion this session surfaced two
gaps:

1. Claude Code's automatic skill-description matching is genuinely
   automatic, but soft "default" wording still reads as optional — an
   agent that stays silent about monitor for a turn isn't clearly told
   that silence is not a valid reason to skip logging.
2. Reports render a full HTML page and cost more tokens than a log
   entry; treating report generation with the same hard-rule strength as
   logging would force an expensive action on every operation, not just
   the cases (before merge, after code changes) where it's warranted.

## Scope

Two files change: `plugins/monitor/commands/init.md` (the injected
block's source text, step 8) and this repo's own `CLAUDE.md` (the Host
project's own dogfood copy of the same block, hand-applied here).
`plugins/monitor/commands/update.md` needs no edit — it references
init.md's block by pointer ("same content as `/monitor:init` step 8"),
not a duplicated copy. `SKILL.md` has no equivalent "When to use it"
section to update — that framing only lives in the injected block.

## Design

Split the block's "When to use it" section into two tiers instead of one
flat list:

- **Logging & task tracking — hard rule.** Explicit "not optional, no
  exceptions" framing: log after every state-changing operation without
  waiting to be asked; track any multi-step unit of work as a task
  (start/update/close) with the same hard-rule treatment; log failures
  too; capture DECISION/WHY/etc for real decisions. States plainly that
  user silence about monitor is not a signal to skip it, and that only an
  explicit per-action instruction to skip overrides these two rules (for
  that action only, not the rest of the session).
- **Reports — default judgment, unchanged strength.** Keeps the existing
  "before every merge" / "after code changes generally" defaults, but
  adds one line explaining *why* reports stay judgment-based rather than
  hard-mandated: they render an HTML page and cost more than a log entry,
  so the agent applies judgment on when one is warranted rather than
  authoring one per logged operation.

The Commands table and Rules section below the "When to use it" split are
unchanged — this spec only touches the "When to use it" content, since
that's the only section carrying enforcement-strength language.

## Testing

No pytest coverage — this is markdown content in a command file and this
repo's own `CLAUDE.md`, not engine logic. Manual verification: after the
edit, run `/monitor:update` in a scratch project and confirm the
regenerated `CLAUDE.md`/`AGENTS.md` block matches the new source text
verbatim; run `python3 scripts/check_thought_leaks.py --level standard`
to confirm no banned dev-history phrasing was introduced.

## Non-goals

- No change to the pending-state hook's actual gate logic (`pending.py`)
  — this spec only changes the prose instructing the agent, not the
  mechanical enforcement already in place via hooks.
- No change to report-generation strength; reports stay exactly as
  strong as they are today, only the surrounding logging/task text
  around them gets harder.
