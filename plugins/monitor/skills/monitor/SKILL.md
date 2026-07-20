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
  logs/     schema.json  operations.log  index.html
```

## Commands
| Command | Does |
|---|---|
| `/monitor:init` | First-time setup: detect project, seed `profile.json`, copy engine into `monitor/scripts/`, generate schema + template + indexes, write `usage.md`. Idempotent. |
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
`profile.json` drives the log `schema.json` and report `template.html`.
Reconcile (`/monitor:update`) only ADDS detected keys/fields and bumps
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
- It validates against `schema.json`, stamps `schemaVersion` + the current branch,
  writes newest-first with a `=`×80 separator, and regenerates the Logs page.
  `branch` is auto-detected; pass `--branch` only to override.
- Log after every state-changing operation (a tight edit+build+commit may be one
  entry). On failure log `status=failure` with the real error. Never log secrets.

## Reporting
- Report only when code changed or a report is explicitly requested — never for
  questions, discussions, or doc tweaks.
- Author from `reports/template.html` into `reports/<date>-<slug>.html`: fill the
  `{{ branch }}` placeholders with the branch the work was done on, **prepend**
  `{date,file,title,description,branch}` to `reports/manifest.json` (index 0), and
  run `render_report.py` to rebuild the Reports index + Dashboard.
- HTML/CSS only, self-contained, no `<script>`; sharp corners
  (`border-radius:0`), dual theme via `prefers-color-scheme`, status via `.tag`
  (`pass`/`warn`/`fail`/`info`) with the label text carrying meaning.
- Sections: Summary · What Was Asked · What Was Done · Evidence (`<pre>`) · Files
  Touched (table) · Risks · Follow-ups · Next Steps.
- Reports are immutable snapshots — never rewrite an old report on a template
  upgrade; only new reports use new sections/KPIs.

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
| **ui-ux-pro-max** | design the report/Logs template + palette | `assets/base_template.html` |
| **superpowers** | `verification-before-completion` gates reports on real build/test output | render but mark **unverified** |
| **graphify** | orientation only — find related code (query/path/explain) | grep / raw reads |
| **openwiki** | doc sync after commits | skip; note in follow-ups |
| **find-skills** | improve skill discovery at init | recommend from this table |
| **copywriting** | polish report prose | write plainly |

The engine never requires any companion — it is stdlib Python. Language servers
and other project-specific plugins are intentionally out of scope.
