---
name: monitor
description: >
  Use when logging an agent operation, writing or updating a project report or
  dashboard, setting up per-project observability, or recovering at session
  start what was already done. Keywords: logging, audit trail, operations log,
  HTML report, dashboard, branch tracking.
---

# monitor

A portable logging + reporting workflow. The plugin ships a generic, stdlib-only
Python 3 engine; each project keeps only its own data + generated assets in a
top-level `monitor/` folder — like `openwiki/` or `graphify-out/`.

## Where things live
```
monitor engine (portable — copy this to port monitor)
  SKILL.md   scripts/   assets/base_template.html
commands/*.md            the slash commands (/monitor:init, :log, :update, …)

<repo>/monitor/          per-project data — created by /monitor:init
  profile.json           SOURCE OF TRUTH (auto-detected, hand-refinable)
  usage.md               companion skills present + how monitor uses each
  .pending.json          pending-state tracker for the enforcement gate (committed, not gitignored)
  index.html             Dashboard (links Reports, Logs, Tasks)
  scripts/               project copy of the engine (run these)
  reports/  template.html  index.html  <date>-<slug>.html  (no manifest — index is scanned)
  logs/     operations.mtr  index.html
  tasks/    tasks.mtr  index.html
```

## Commands
| Command | Does |
|---|---|
| `/monitor:init` | First-time setup: detect project, seed `profile.json`, copy engine into `monitor/scripts/`, generate template + indexes, write `usage.md`. Idempotent. |
| `/monitor:update` | Re-detect + reconcile `profile.json` additively, re-copy engine, regenerate assets, refresh `usage.md`. Backward compatible. |
| `/monitor:log` | Append one operation entry to the log. |
| `/monitor:report` | Author one HTML report + rebuild the Reports index. |
| `/monitor:record` | Log **and** (when code changed) report, in one step. |
| `/monitor:search <query>` | Search the operations log by keyword; plain-text output. |
| `/monitor:status` | Show open tasks, recent activity, pending items, and next steps directly in chat. Never writes a file. |
| `/monitor:task-start "<title>"` | Start a new lifecycle-tracked task; prints the generated `task_id`. |
| `/monitor:task-update <id>` | Append a status/metrics update to an existing task. |
| `/monitor:task-close <id>` | Close a task with a terminal status (success/failed/cancelled). |
| `/monitor:clean-logs <N>` | Delete the oldest N log entries; re-render Logs. |
| `/monitor:clean-reports <N>` | Delete the oldest N reports; re-render Reports + Dashboard. |
| `/monitor:clean-tasks <N>` | Delete the oldest N tasks (all their events); re-render Tasks + Dashboard. |

Commands are agent-only. Internally the agent runs the engine via
`python3 monitor/scripts/<script>.py [args]` (each resolves its own project
root). Run any script with `--help` for its flags.

## Precondition — init first
Every command except `/monitor:init` requires `monitor/profile.json`. If it is
missing, do not run any engine script — prompt for `/monitor:init` and stop. The
engine scripts also fail fast (exit 2) when it is absent; only `profile.py`
(which creates it) is exempt.

## Monitor's job: log, report, and track tasks
Monitor never detects a project's language, guesses its build/test commands,
or otherwise inspects what the project does. That's guessing, not recording
or presenting — out of scope, whether the project is brand new or years old.
`profile.json` only auto-fills the project's directory name (to brand pages)
plus the report KPI list. If an agent needs real project orientation to write
a good report, use a companion skill like `graphify` for that — not monitor.

## profile.json evolves additively
Reconcile (`/monitor:update`) only ADDS detected keys/fields and bumps
`profileVersion`; it never changes, removes, or renames existing keys. The
profile is always a superset of every prior version — that is what keeps upgrades
backward compatible. The log schema lives in code in `logger.py` (see Logging
below), identical across every project.

## Branch tracking
Pages (Dashboard/Reports/Logs) show the **current** branch (SVG git-branch chip +
a KPI). Each log entry and report records the branch its **change was made on** —
so pages and entries legitimately differ once you switch branches. The engine
detects the branch (`git rev-parse --abbrev-ref HEAD`); outside a repo it shows
`no branch`, on a detached HEAD `detached@<sha>`. Entries/reports predating the
field show no chip.

## Logging
- Log through the engine only — never hand-edit `operations.mtr`:
  `logger.py --operation <kebab> --tool <Tool> --summary "<one line>" --status success|partial|failure [--details ...] [--files a b] [--task-id <id>] [--branch <name>] [--last-commit-hash <sha>] [--set k=v]`.
- The schema is **locked in code** (`REQUIRED`/`LEVELS`/`STATUSES` constants in
  `logger.py`), identical across every project. It
  validates required fields and the `level`/`status` enums before writing.
- **Every field is sanitized before it reaches the log, no exceptions.**
  `logger.py`'s `sanitize()` runs on every field of every entry — strips
  control characters, flattens real newlines to spaces. This exists because
  a field can pick up garbage you didn't intend: e.g. writing an example
  shell command in backticks inside `--details` gets command-substituted by
  the shell before `logger.py` ever sees it, splicing that command's raw
  output (including ANSI escape codes) into the field. **Avoid backticks
  around example commands in `--details`/`--summary`** — use single quotes
  or no quoting-sensitive characters at all — since sanitize() cleans up
  control bytes but can't undo a command that already ran.
- Each entry is written newest-first with a `=`×80 separator and stamps the
  current branch; `render_logs.py` regenerates the Logs page from the log
  text. `branch` is auto-detected; pass `--branch` only to override.
- **`--details` formatting is the caller's job, not the renderer's.** Storage
  and rendering are dumb by design: `format_list_block` decodes a literal
  `\n`-per-point convention into a real `<ol>`/`<ul>` (numbered markers →
  `<ol>`, bullet markers or plain labeled lines → `<ul>`), but it only
  reformats what it's given — a freehand paragraph renders as a paragraph.
  Always write `--details` as one point per line (`DECISION: ...\nWHY: ...`
  or `1. ...\n2. ...` etc.), never as run-on prose, so it never lands as a
  giant paragraph on the Logs page.
- **Default behavior, no prompting needed:** log after every state-changing
  operation, including small ones (one file edit, one command run, one config
  tweak) — a tight edit+build+commit may be one entry, but don't skip logging
  just because the change was small. On failure log `status=failure` with the
  real error. Never log secrets.

### Context capture — write `--details` so a new agent can pick up cold
The log is the recovery path when a different agent (or a future you) opens this
project with zero memory of the session. For any operation that involved a
decision — not a pure mechanical edit — fill `--details` with a labeled,
single-line-per-field answer to whichever of these apply. Skip fields with
nothing to say; don't pad:
- `DECISION:` the concrete choice made (what, not just "fixed it").
- `WHY:` the reasoning — constraints, tradeoffs, alternatives considered and
  why they were rejected. This is the field that saves the most re-derivation
  time; never leave a real decision without it.
- `ARCHITECTURE:` what changed structurally — components, data flow,
  contracts, schemas, file responsibilities — if anything did.
- `NEXT:` the immediate next step, stated as an action, not a vague intent.
- `GAPS:` known issues, TODOs, deferred work, open questions, anything
  incomplete or unverified.
- `ASSUMPTIONS:` anything taken on faith that the next agent should verify
  before building further on it.
For a trivial mechanical change (typo, formatting, rename with no behavior
change), a plain `--summary` with no `--details` is correct — verbose entries
for non-decisions waste tokens on every future read of the log. Match verbosity
to how much a cold-start agent would actually need.
Every log entry automatically records the git `HEAD` short sha at the moment
it's logged (`last_commit_hash`, captured by `logger.py` itself — no manual
step, works even for entries the user triggers by hand). It's searchable via
`/monitor:search <sha>` and pins each entry to the commit the working tree
was at when it was logged.

**Formatting — never write a run-on list.** Join fields with a literal `\n`
inside the `--details` string, **one field per line** — do **not** write
`DECISION: x. WHY: 1. reason one. 2. reason two.` as one sentence; that is
exactly the "1. some fix. 2. next fix." run-on this convention exists to
prevent. The Logs page splits on those `\n`s and renders one `<li>` per line
as a real `<ul>` automatically — so each line must already be one complete,
self-contained point. If a field has multiple genuinely separate points (e.g.
two distinct gaps), give it multiple lines with the same label repeated
rather than numbering inside one line:
```
--details "DECISION: Cache reads through Redis instead of an in-process LRU.\nWHY: Redis was already a dependency, so this avoids adding one.\nWHY: TTL-based eviction matches the cache's existing semantics.\nGAPS: No metrics on hit rate yet.\nGAPS: Backfill script for old cache keys not written."
```
Never number or bullet *within* a single line — one point, one line, one
label.

## Reporting
- Report only when code changed or a report is explicitly requested — never for
  questions, discussions, or doc tweaks.
- **Default behavior, before every merge:** if the current branch is about to
  be merged into its base branch (user says "merge", "ready to merge", opens a
  PR for merge, or runs a merge command), generate a report first if the branch
  has code changes not yet covered by one — summarizing the branch's work as a
  single pre-merge report. Don't ask whether to report; do it, then proceed
  with the merge.
- Author from `reports/template.html` into `reports/<date>-<slug>.html`: fill the
  `{{ branch }}` placeholders with the branch the work was done on. Fill
  `{{ date }}` yourself with today's date (`YYYY-MM-DD`) — the "Generated"
  chip, which no script ever substitutes; an unfilled `{{ date }}` ships
  verbatim into the published report. Fill `{{ date_created }}` yourself as
  well, with the date the underlying work began (often earlier than
  `{{ date }}`). Leave `{{ last_modified }}` alone — it is the one date
  placeholder stamped automatically, by `render_report.py --lock-report` at
  the end of authoring. Then run
  `render_report.py` to rebuild the Reports index + Dashboard. No manifest to
  update — the index is scanned fresh from `reports/*.html` every time, reading
  each report's own `<h1>`/Branch chip/Summary directly out of the file.
- **Design is locked, independent of content requests.** A request about the
  *content* — audience, reading level, tone, language, "explain it like I'm
  11", humor, formality — changes only the prose written into each section.
  It never touches the `<style>` block, palette, layout, class names, or
  structure; those come from `mlib.PALETTE_CSS` and are identical across
  every report regardless of who it's written for. Right after authoring a
  report (and before indexing it), run `render_report.py --lock-report
  reports/<file>.html` — it force-overwrites the file's `<style>` block back
  to the canonical palette and strips any stray `<script>` tag, so even if a
  content-tone instruction bled into the design during authoring, the
  published file can't ship off-theme. This is a one-time correction on the
  new file only — never run it against old reports, that would violate the
  immutable-snapshot rule below.
- HTML/CSS only, self-contained, no `<script>` — except the Dashboard
  (`monitor/index.html`), which carries one small self-contained script for its
  search box, the single deliberate exception; sharp corners
  (`border-radius:0`), dual theme via `prefers-color-scheme`, status via `.tag`
  (`pass`/`warn`/`fail`/`info`) with the label text carrying meaning.
- Sections: Summary · What Was Asked · What Was Done · **Decisions & Rationale**
  · Evidence (`<pre>`) · Files Touched (table) · Risks · Gaps & Assumptions ·
  Follow-ups · Next Steps.
- **Decisions & Rationale** is the recovery section — one entry per real
  decision made on the branch: what was decided, why (alternatives considered
  and rejected), and what it touched architecturally. Pull this straight from
  the `DECISION:`/`WHY:`/`ARCHITECTURE:` fields already captured in the
  branch's log entries — don't re-derive them from scratch, that's the whole
  point of logging them as you go.
- **Gaps & Assumptions** carries forward each entry's `GAPS:`/`ASSUMPTIONS:`
  fields plus anything still open. A new agent reading only the report (not
  the raw log) should be able to resume work without asking what's unfinished.
- **Next Steps is about the project, not the authoring turn.** Every entry
  must be a concrete next step for the code or the branch (e.g. "add retry
  handling to X", "rebuild main"). It must never describe what the authoring
  agent itself is about to do in chat — asking the user something, awaiting
  approval, presenting options. Those are mid-conversation actions, not
  outcomes a reader can act on days later, and a report is read after the
  turn that wrote it has already ended. If there's genuinely no next step,
  omit the section rather than filling it with a meta-statement about the
  conversation.
- **Formatting — one point per `<li>`, never a numbered sentence inside a
  `<p>`.** `template.html` already gives What Was Done, Decisions & Rationale,
  Risks & Regressions, Gaps & Assumptions, Follow-ups, and Actionable Next
  Steps as `<ul>`/`<ol class="steps">` — use them: one `<li>` per decision,
  gap, risk, or step. Writing `<p>1. did x. 2. did y.</p>` defeats the
  template's list markup and produces exactly the wall-of-text this workflow
  exists to avoid. Only Summary and What Was Asked stay prose `<p>` — they're
  one coherent statement, not a list of points.
- Reports are immutable snapshots — never rewrite an old report on a template
  upgrade; only new reports use new sections/KPIs.

## Tasks
A third tracked entity, separate from logs and reports: a lifecycle-tracked
unit of work with self-reported metrics, backed by `monitor/tasks/tasks.mtr`
(same append-only block format as `operations.mtr`) and rendered to a
paginated `monitor/tasks/index.html`, linked as the third Dashboard tab.

- **Lifecycle:** `open → in_progress → (needs_approval | needs_retry |
  blocked)* → success | failed | cancelled`. The first 5 are non-terminal
  (valid on `/monitor:task-start`/`/monitor:task-update`); the last 3 are
  terminal (valid only on `/monitor:task-close`).
- **Metrics are self-reported, not instrumented.** `tokens`, `credits`,
  `cost`, `skills_used`, `tools_called` are CLI flags the agent fills in
  from its own knowledge of what it did — the engine is stdlib Python with
  no access to the real session transcript, so it cannot introspect actual
  token counts or which skills/tools actually ran. Same trust model
  `--details` already uses.
- **Metrics accumulate.** Every `task-update`/`task-close` call's numeric
  metrics add to the task's running total; `skills_used`/`tools_called`
  union (dedup) across calls.
- **Log entries can reference a task.** `logger.py --task-id <id>` stores a
  foreign key into `tasks.mtr` on that log entry, rendered as a chip on the
  Logs page — purely a cross-reference, not required.
- **Commands:** `/monitor:task-start "<title>"` (returns and prints the
  generated `task_id` — relay it to the user, you need it for every
  subsequent call), `/monitor:task-update <id> --status ...`,
  `/monitor:task-close <id> --status success|failed|cancelled`.

### Integration points
- This harness's own `TaskCreate`/`TaskUpdate`/`TaskGet` calls map naturally
  onto `task-start`/`task-update`/`task-close` — when already tracking a
  task with the harness's native tool, mirror the same lifecycle into
  monitor so it's recoverable from the log/report system too, not just the
  harness's own ephemeral task state.
- `superpowers:subagent-driven-development`'s per-task dispatch loop
  (ledger file, one task per implementer round) maps the same way: a
  `task-start` when a task's implementer is dispatched, `task-update` on
  each fix-loop round, `task-close` when the ledger marks it done.

## Memory — apply this policy without re-reading SKILL.md every session
`/monitor:init` (and `/monitor:update`) save a compressed version of the
Logging and Reporting defaults above to the agent's persistent memory, as
`feedback`-type entries (see the memory system's own conventions for format).
Once that memory exists, treat it as authoritative for *when* to log/report;
consult it instead of re-reading this file in full — that's the token saving.
Still open this file when a command's exact flags/behavior are needed, or when
memory is missing/stale (e.g. after installing monitor into a new project that
has no memory yet — run `/monitor:init` there to seed it). The memory entries
themselves stay short (rule + why + how-to-apply, caveman-compressed); the
*log and report content itself* stays verbose per "Context capture" above —
compress the reminder, not the record.

## Common mistakes
| Mistake | Reality |
|---|---|
| Reporting a discussion or doc tweak "to be safe" | Reports are for code changes only. A rules/doc edit is not a code change — log it, don't report it. |
| Hand-editing `operations.mtr` to fix a typo | Always go through `logger.py`. The Logs page is regenerated from the log; hand-edits desync the two and can corrupt parsing. |
| Rewriting an old report after a template change | Reports are immutable snapshots. Upgrade forward — only new reports get new sections/KPIs. |
| Running any command before `/monitor:init` | Everything needs `profile.json`. Init first; the scripts exit 2 otherwise. |
| Sourcing Files-Touched from graphify | graphify has no diff capability. Files-Touched always comes from `git diff --name-only` or the operation's explicit `--files`. |
| Putting task info in `--details` on a log entry | Tasks are a separate tracked entity, not a log field. Use `/monitor:task-start`/`update`/`close`; cross-reference with `logger.py --task-id`. |
| Assuming `/monitor:search` only covers logs | It covers logs, reports, and tasks by default (`--scope all`); narrow with `--scope logs|reports|tasks` if you only want one source. |
| Writing a file for `/monitor:status` | It's chat-only by design — a status snapshot, not a durable artifact. Never create a report, dashboard entry, or any other file for it. |

## Status

`/monitor:status` gives a chat-only project snapshot — open tasks, recent
activity, pending items, and next steps — with no file written. `status.py`
prints one JSON object to stdout; every field in it is extracted
mechanically, nothing is inferred by the script:
- `open_tasks` — every non-terminal task (same set `pending.open_tasks()`
  already returns for the pending-state gate).
- `recent_logs` — the last `--log-limit` (default 5) log entries.
- `pending` — `pending_logs`/`pending_report`/`pending_task_signal` straight
  from `monitor/.pending.json`, the same data the pending-state gate reads.
- `current_activity` — the most recently started open task's title if one
  exists, else the most recent log entry's summary, else `none`.
- `next_steps` — `NEXT:`/`GAPS:`/`ASSUMPTIONS:` lines regex-extracted from
  the last `--log-limit` entries' `--details` text (the same labeled-field
  convention logging already uses) — never invented, only ever what a log
  entry already recorded.
- `git` — current branch, uncommitted/untracked file counts, and the last
  `--commit-limit` (default 5) commit subjects.

The agent's only job is to read this JSON and answer in chat, organized as
What Happened / Currently Working On / Pending & Queued / Next Steps For
You — formatting already-deterministic data, not judging or inventing it.

## Pending-state enforcement

Two Claude Code hooks (installed by `/monitor:init`/`/monitor:update` into
the project's `.claude/settings.json`) back a soft, real reminder instead of
pure discretion. A `PostToolUse` hook (matcher `Bash|Write`) fires `pending.py
hook-post-tool-use` after every tool call and self-filters by inspecting
`tool_input`: a `Bash` call running `git commit`/`merge`/`rebase` records it
in `monitor/.pending.json`'s `pending_logs`/`pending_report`; a `Write` call
to a `*.md` file under any `plans/`/`specs/` directory records a
`pending_task_signal` **only if no task is currently open** — a heuristic
proxy for "multi-step work may have just started," not a guarantee. A
`UserPromptSubmit` hook fires `pending.py hook-user-prompt-submit` on your
next turn — if anything is pending, its `[Warn!]` text becomes injected
context:

- **Logs/report pending** → surface it to the user and get a Y/N before
  continuing. **Y** → work through `monitor/.pending.json`'s `pending_logs`
  (one `/monitor:log` per entry) and `pending_report` (one `/monitor:report`
  covering `git log <since_sha>..HEAD`), then continue the user's original
  request. **N** → say so, leave `.pending.json` untouched (it stays pending
  and reminds again next turn), and do whatever the user asks instead.
- **Open tasks** (`open_tasks()`, read fresh from `tasks.mtr` on every call,
  never stored) and/or a **pending task-start nudge** → surfaced as plain
  informational text, never a Y/N question — starting/closing a task is
  never something a Y/N answer resolves. `pending_task_signal` clears
  automatically the moment a task starts (`tasks.py`'s `start_task()` calls
  `pending.clear_task_signal()`); open tasks stop appearing the moment they
  close, with no separate clearing step needed since they're recomputed
  from `tasks.mtr` each time.

**Clearing more than one `pending_logs` entry.** `logger.py` clears the
pending entry whose sha matches the entry it just wrote, and that sha
defaults to the *current* `HEAD`. So when several commits are pending at
once, pass `--last-commit-hash <that entry's sha>` to `/monitor:log` for
every entry that isn't `HEAD` — otherwise each catch-up log clears (at best)
whatever `HEAD` happens to be and the older entries never drain.

Commits that touch **only** `monitor/` paths are not tracked as pending —
committing monitor's own log/report output would otherwise create a pending
entry demanding a log, whose commit creates another, forever.

`monitor/.pending.json` is committed like the rest of `monitor/` — it's
per-branch state, not local scratch. `logger.py` and `render_report.py`
(on `--lock-report`) clear the matching entries automatically on success;
nothing else should ever hand-edit this file.

## Companion skills (all optional, with fallbacks)
`usage.md` records which are present and how monitor uses each.

| Skill | Role | Fallback if absent | Install (project-scoped preferred) |
|---|---|---|---|
| **ui-ux-pro-max** | UI is fixed (`mlib.PALETTE_CSS`), identical across every project | n/a | Plugin marketplace `nextlevelbuilder/ui-ux-pro-max-skill`, plugin `ui-ux-pro-max` |
| **superpowers** | `verification-before-completion` gates reports on real build/test output | render but mark **unverified** | Plugin marketplace `anthropics/claude-plugins-official`, plugin `superpowers` |
| **openwiki** | doc sync after commits | skip; note in follow-ups | Plugin marketplace `SoulKyu/openwiki-cc`, plugin `openwiki` |
| **find-skills** | improve skill discovery at init | recommend from this table | `npx skills add vercel-labs/skills@find-skills` (no `-g`) |
| **copywriting** | polish report prose | write plainly | `npx skills add coreyhaines31/marketingskills@copywriting` (no `-g`) |
| **graphify** | orientation only — find related code (query/path/explain) | grep / raw reads | `pip install graphifyy && graphify install` — **global only**, no project-scoped install exists |

The three plugins install project-scoped via `.claude/settings.json`'s
`extraKnownMarketplaces` (registers the marketplace source so every clone of
the repo gets it, not just the machine that ran init) plus `enabledPlugins`
(turns the plugin on). The two `npx skills` packages install project-scoped by
omitting `-g` — they land under the project's own skills path and are
committed with the repo. `graphify` has no project-scoped install path in its
own installer; it always goes to `~/.claude/skills/graphify` via `pip`/`pipx`,
so it's the one companion that's necessarily global. See "Installing
companions" in `/monitor:init` for the actual install step.

The engine never requires any companion — it is stdlib Python. Language servers
and other project-specific plugins are intentionally out of scope.
