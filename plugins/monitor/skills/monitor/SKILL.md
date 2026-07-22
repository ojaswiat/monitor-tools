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
  index.html             Dashboard (links Reports + Logs)
  scripts/               project copy of the engine (run these)
  reports/  template.html  manifest.json  index.html  <date>-<slug>.html
  logs/     operations.log  index.html
```

## Commands
| Command | Does |
|---|---|
| `/monitor:init` | First-time setup: detect project, seed `profile.json`, copy engine into `monitor/scripts/`, generate template + indexes, write `usage.md`. Idempotent. |
| `/monitor:update` | Re-detect + reconcile `profile.json` additively, re-copy engine, regenerate assets, refresh `usage.md`. Backward compatible. |
| `/monitor:log` | Append one operation entry to the log. |
| `/monitor:report` | Author one HTML report + rebuild the Reports index. |
| `/monitor:record` | Log **and** (when code changed) report, in one step. |
| `/monitor:clean-logs <N>` | Delete the newest N log entries; re-render Logs. |
| `/monitor:clean-reports <N>` | Delete the newest N reports; re-render Reports + Dashboard. |

Commands are agent-only. Internally the agent runs the engine via
`python3 monitor/scripts/<script>.py [args]` (each resolves its own project
root). Run any script with `--help` for its flags.

## Precondition — init first
Every command except `/monitor:init` requires `monitor/profile.json`. If it is
missing, do not run any engine script — prompt for `/monitor:init` and stop. The
engine scripts also fail fast (exit 2) when it is absent; only `profile.py`
(which creates it) is exempt.

## profile.json evolves additively
`profile.json` carries project identity (name, VCS, language, build/test
commands) and the report KPI list. The log schema is **not** profile-driven —
it's locked in code in `logger.py` (see Logging below), identical across every
project. Reconcile (`/monitor:update`) only ADDS detected keys/fields and bumps
`profileVersion`; it never changes, removes, or renames existing keys. The
profile is always a superset of every prior version — that is what keeps upgrades
backward compatible.

## Branch tracking
Pages (Dashboard/Reports/Logs) show the **current** branch (SVG git-branch chip +
a KPI). Each log entry and report records the branch its **change was made on** —
so pages and entries legitimately differ once you switch branches. The engine
detects the branch (`git rev-parse --abbrev-ref HEAD`); outside a repo it shows
`no branch`, on a detached HEAD `detached@<sha>`. Entries/reports predating the
field show no chip.

## Logging
- Log through the engine only — never hand-edit `operations.log`:
  `logger.py --operation <kebab> --tool <Tool> --summary "<one line>" --status success|partial|failure [--details ...] [--files a b] [--task ...] [--branch <name>] [--set k=v]`.
- The schema is **locked in code** (`REQUIRED`/`LEVELS`/`STATUSES` constants in
  `logger.py`) — not profile-driven, identical across every project. It
  validates required fields and the `level`/`status` enums before writing.
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
  `{{ branch }}` placeholders with the branch the work was done on, **prepend**
  `{date,file,title,description,branch}` to `reports/manifest.json` (index 0), and
  run `render_report.py` to rebuild the Reports index + Dashboard.
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
- HTML/CSS only, self-contained, no `<script>`; sharp corners
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
| Hand-editing `operations.log` to fix a typo | Always go through `logger.py`. The Logs page is regenerated from the log; hand-edits desync the two and can corrupt parsing. |
| Rewriting an old report after a template change | Reports are immutable snapshots. Upgrade forward — only new reports get new sections/KPIs. |
| Running any command before `/monitor:init` | Everything needs `profile.json`. Init first; the scripts exit 2 otherwise. |
| Sourcing Files-Touched from graphify | graphify has no diff capability. Files-Touched always comes from `git diff --name-only` or the operation's explicit `--files`. |

## Companion skills (all optional, with fallbacks)
`usage.md` records which are present and how monitor uses each.

| Skill | Role | Fallback if absent |
|---|---|---|
| **ui-ux-pro-max** | not used for design — UI is fixed (`mlib.PALETTE_CSS`), identical across every project | n/a |
| **superpowers** | `verification-before-completion` gates reports on real build/test output | render but mark **unverified** |
| **graphify** | orientation only — find related code (query/path/explain) | grep / raw reads |
| **openwiki** | doc sync after commits | skip; note in follow-ups |
| **find-skills** | improve skill discovery at init | recommend from this table |
| **copywriting** | polish report prose | write plainly |

The engine never requires any companion — it is stdlib Python. Language servers
and other project-specific plugins are intentionally out of scope.
