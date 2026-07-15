---
name: monitor
description: >
  Use when logging agent operations or writing HTML reports for a project.
  Maintains a project-local monitor/ folder (Dashboard + Reports + Logs) whose
  report template and log schema are project-specific and evolve additively.
  Commands: /monitor (log + report), /monitor:init, /monitor:update,
  /monitor:clean-logs <N>, /monitor:clean-reports <N>.
---

# monitor

A portable logging + reporting workflow. The **plugin** (this folder,
`.claude/skills/monitor/`) ships the generic engine; each project keeps only its
own data + generated assets in a top-level **`monitor/`** folder — exactly like
`openwiki/` or `graphify-out/`.

## Where things live
```
.claude/skills/monitor/   (portable engine — copy this to port monitor)
  SKILL.md                 these rules
  scripts/                 monitor_lib, profile, logger, render_logs,
                           render_report, clean   (Python 3, stdlib only)
  assets/base_template.html  fallback report template
.claude/commands/monitor*  the slash commands (copy alongside the skill)

<repo>/monitor/            (per-project data — created by /monitor:init)
  profile.json             SOURCE OF TRUTH (auto-detected, hand-refinable)
  usage.md                 which companion skills are present + how monitor uses them
  index.html               Dashboard (links Reports + Logs)
  scripts/                 project copy of the engine (run these)
  reports/  template.html  manifest.json  index.html  <date>-<slug>.html
  logs/     schema.json  operations.log  index.html
```

## Precondition — init before anything else
Every command except `/monitor:init` requires the project to be initialised,
marked by the presence of **`monitor/profile.json`**. If it is missing, the
command must **not** run any engine script or take any action — it prompts the
user to run `/monitor:init` and stops. As defense-in-depth, the engine scripts
(logger, clean, render_logs, render_report) also fail fast (exit 2) when
`monitor/profile.json` is absent; only `profile.py` (which creates it) is exempt.

## Commands
| Command | Does |
|---|---|
| `/monitor:init` | First-time setup: detect project, seed `profile.json`, copy engine into `monitor/scripts/`, generate `schema.json` + `template.html` + indexes, write `usage.md`. Idempotent. |
| `/monitor:update` | Re-detect + **reconcile** `profile.json` additively (new fields, bump `profileVersion`), re-copy the engine, regenerate `schema.json`/`template.html`/indexes, refresh `usage.md`. Backward compatible. |
| `/monitor` | Log **and** report in one step, from the user's prompt: append a log entry AND (when code changed) write a report. |
| `/monitor:clean-logs <N>` | Delete the newest N log entries; re-render the Logs page. |
| `/monitor:clean-reports <N>` | Delete the newest N reports (files + manifest); re-render the Reports page + Dashboard. |

Commands are agent-only (invoked in the assistant interface, never from a shell).
Internally the agent runs the Python engine via Bash:
`python3 monitor/scripts/<script>.py [args]` (each resolves its own project root).

## profile.json — project-specific, evolves additively
`profile.json` drives the log `schema.json` and report `template.html`. It is
auto-seeded on init and refinable by hand. Reconcile (`/monitor:update`) is
**strictly additive**: new detected keys/fields are added and stamped with the
new `profileVersion`; existing keys are never changed, removed, or renamed. That
is what keeps upgrades backward compatible — the profile is always a superset of
every prior version.

## Branch tracking
Every page shows the **current branch** in its masthead (an SVG git-branch chip,
never an emoji) plus a *Current branch* KPI on the Dashboard, Reports, and Logs
pages. Each **log entry** records the branch its operation was made on, and each
**report** records the branch its work was done on — pages show *current*, entries
show *where the change happened*, and the two legitimately differ once you switch
branches. The engine detects the branch itself (`git rev-parse --abbrev-ref HEAD`);
outside a repo it degrades to a neutral `no branch`, and on a detached HEAD it
reports `detached@<short-sha>`. Entries and reports predating the field simply
show no chip.

## Logging rules
1. Never hand-edit `operations.log`. Always log through the engine:
   `python3 monitor/scripts/logger.py --operation <kebab> --tool <Tool> --summary "<one line>" --status success|partial|failure [--details "..."] [--files a b] [--task "..."] [--level INFO] [--branch <name>] [--set key=value]`.
2. It validates against `logs/schema.json` (required fields + enums), stamps the
   `schemaVersion` **and the current branch**, writes newest-first with a `=`×80
   separator, and regenerates the Logs page. On failure, log `status=failure`
   with the real error. `branch` is detected automatically — pass `--branch` only
   to override it (e.g. logging work done on another branch).
3. Log after every operation that changes state; a tight sequence
   (edit+build+commit) may be one entry. Never log secrets/tokens/credentials.
4. At session start / after compaction, read the top of `operations.log` (or the
   Logs page) to recover what was already done.

## Reporting rules
1. Create reports only when code changed or a report is explicitly requested —
   never for questions, discussions, or doc tweaks.
2. Author each report from `monitor/reports/template.html` into
   `monitor/reports/<date>-<slug>.html` — fill its `{{ branch }}` placeholders
   (masthead chip + Branch meta chip) with the branch the work was done on; then
   **prepend** `{date,file,title,description,branch}`
   to `reports/manifest.json` (newest-first — insert at index 0) and run
   `render_report.py` to rebuild the Reports
   index + Dashboard. Only HTML/CSS, self-contained, no external assets, no
   `<script>`; **sharp corners** (`border-radius:0`), dual theme via
   `prefers-color-scheme`, tabular numerals, status via `.tag` classes
   (`pass`/`warn`/`fail`/`info`) with the label text carrying meaning.
3. Sections: Summary · What Was Asked · What Was Done · Evidence (`<pre>`) ·
   Files Touched (table) · Risks · Follow-ups · Actionable Next Steps.
4. Reports are immutable snapshots — never rewrite an old report on a template
   upgrade; only new reports use new sections/KPIs.

## Companion skills (recommended — all optional, with fallbacks)
`usage.md` records which of these are present in the project and how monitor uses
each. Use them if available; degrade gracefully if not.

| Skill | Role in monitor | Fallback if absent |
|---|---|---|
| **ui-ux-pro-max** | design the report/Logs template + palette | use `assets/base_template.html` |
| **superpowers** | `verification-before-completion` gates reports on real build/test output; plans/reviews feed report content | render but mark **unverified** |
| **graphify** | orientation only — find relevant/related code (query/path/explain) | raw file reads / grep |
| **openwiki** | doc sync after commits | skip; note in follow-ups |
| **find-skills** | improve skill *discovery* at init (surface installable skills) | recommend from this table |
| **copywriting** | polish report prose | write plainly |

**Files-touched is never sourced from graphify.** graphify is a static AST
knowledge graph (query/path/explain/diagnose) with no diff or files-changed
capability, so a report's / log entry's Files-Touched list always comes from
`git diff --name-only` (or the operation's explicit `--files`), whether or not
graphify is present. **find-skills** only affects *discovery quality* at init —
whether extra installable skills get surfaced; monitor recommends the companion
skills from the table above either way, so its absence is a near-no-op.

Language servers and other project-specific plugins are intentionally not part of
monitor. The engine itself never requires any companion — it is stdlib Python.
