---
description: Initialise the monitor plugin for this project (idempotent).
---

Initialise **monitor** for this project. Read the **monitor** skill (`SKILL.md`) first.

1. If `monitor/profile.json` already exists, switch to verify/repair mode: report
   what is present and only create what is missing (do not clobber data).
2. **Seed the profile and copy the engine** into the project so it is
   self-contained. Run these as ONE block so `$ENGINE` (which locates the engine
   whether monitor is installed as a plugin or copied into `.claude/skills/`)
   stays set:
   ```bash
   ENGINE="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/monitor}"; [ -z "$ENGINE" ] && ENGINE=".claude/skills/monitor"
   python3 "$ENGINE/scripts/profile.py" --project-root .
   mkdir -p monitor/scripts && cp "$ENGINE"/scripts/*.py monitor/scripts/
   ```
   (`profile.py` detects language, build/test commands, VCS.)
4. Generate project-specific assets from the profile:
   `python3 monitor/scripts/render_report.py` (writes `reports/template.html`,
   `reports/index.html`, `index.html`, seeds `reports/manifest.json`) and
   `python3 monitor/scripts/render_logs.py` (creates `monitor/logs/log.db`
   with the locked schema if it doesn't exist yet, and an empty-state Logs
   page).
5. Probe companion skills (graphify, superpowers, openwiki, ui-ux-pro-max,
   find-skills, copywriting) via `.claude/settings.json` enabledPlugins and the
   skills folder. Write `monitor/usage.md`: for each, PRESENT/ABSENT and how
   monitor uses it here (from the SKILL.md companion table). For absent high-fit
   skills, recommend them with the enable command — installation stays
   user-gated (on approval, run only their init, e.g. `graphify update .`,
   `/openwiki:wiki init`).
6. Ensure `.gitignore` contains `monitor/scripts/__pycache__/`.
7. Add or update a **monitor** section in the project's `CLAUDE.md` (create the
   file if it does not exist). Write it between
   `<!-- monitor:start -->` / `<!-- monitor:end -->` markers so re-running
   `/monitor:init` or `/monitor:update` replaces the block instead of
   duplicating it. Content:
   ```markdown
   <!-- monitor:start -->
   ## monitor — operations log + reports

   This project has **monitor** installed: a local logging/reporting workflow.
   It keeps a project-local `monitor/` folder — a Dashboard linking a **Reports**
   page (one self-contained HTML report per task/change) and a **Logs** page
   (rendered from `monitor/logs/log.db`, a locked-schema SQLite store). Rules for using it live in
   the skill at `SKILL.md` (or `$CLAUDE_PLUGIN_ROOT/skills/monitor/SKILL.md`
   when installed as a plugin) — read it before running any command below.

   **When to use it (defaults — no need to ask first):**
   - **Log after every state-changing operation, including small ones** (one
     file edit, one command run, one config tweak) — run `/monitor:log` or
     `/monitor:record`. A tight edit+build+commit can be one entry, but don't
     skip logging just because the change was small.
   - **Generate a report before every merge.** Before merging the current
     branch into its base branch, run `/monitor:report` (or `/monitor:record`)
     if the branch has code changes not yet covered by a report. Do this by
     default when asked to merge — don't wait to be asked for a report
     separately.
   - After code changes generally — write a report with `/monitor:report` (or
     via `/monitor:record`). Never report a discussion or doc-only tweak.
   - On failure, log it anyway with `status=failure` and the real error —
     don't skip logging just because the operation didn't succeed.
   - **For real decisions, log the reasoning, not just the outcome.** In
     `--details`, capture (whichever apply) `DECISION:` what was chosen,
     `WHY:` alternatives considered and rejected, `ARCHITECTURE:` what
     structurally changed, `NEXT:` the immediate next step, `GAPS:` known
     issues/TODOs, `ASSUMPTIONS:` anything unverified. A trivial mechanical
     edit just needs `--summary`, no `--details`. Reports pull their
     **Decisions & Rationale** and **Gaps & Assumptions** sections straight
     from these fields — see `SKILL.md` for the full convention.

   **Commands:**
   | Command | Does |
   |---|---|
   | `/monitor:init` | First-time setup (idempotent). Run once per project. |
   | `/monitor:log` | Append one operation entry to the log. |
   | `/monitor:report` | Author one HTML report + rebuild the Reports index. |
   | `/monitor:record` | Log, and if code changed, report — in one step. |
   | `/monitor:update` | Re-detect + additively reconcile the profile, refresh assets. |
   | `/monitor:clean-logs <N>` | Delete the newest N log entries; re-render Logs. |
   | `/monitor:clean-reports <N>` | Delete the newest N reports; re-render Reports + Dashboard. |

   **Rules:**
   - Every command except `/monitor:init` requires `monitor/profile.json` to
     exist — it fails fast otherwise. Run init first if it's missing.
   - Never hand-edit `monitor/logs/log.db` — always go through
     `logger.py` (via `/monitor:log` or `/monitor:record`); the schema is
     locked (fixed columns, CHECK constraints on `level`/`status`) and never
     migrated — a bad manual write can violate it outright.
   - Reports are immutable snapshots — never rewrite an old report when the
     template changes; only new reports pick up new sections.
   - `monitor/profile.json` evolves additively only — `/monitor:update` adds
     detected fields, never removes or renames existing ones.
   <!-- monitor:end -->
   ```
8. **If a persistent memory system is available to you** (a memory directory
   you write files to and that is loaded back into future sessions — check
   for one before assuming it's absent), save the logging/reporting policy
   there now as `feedback`-type memory so future sessions apply it without
   re-reading `SKILL.md` in full. Keep the memory content itself compressed
   (rule + why + how-to-apply, one entry per policy, no restatement of the
   full `SKILL.md` prose) — the verbosity belongs in the logs/reports
   themselves, not in the reminder to write them. Save at minimum:
   - **When to log**: after every state-changing operation including small
     ones; never skip because a change was small; log failures too with the
     real error. Why: this project uses monitor for session-to-session
     context recovery — a gap in the log is a gap a future agent can't fill.
   - **What to put in `--details`**: `DECISION:`/`WHY:`/`ARCHITECTURE:`/
     `NEXT:`/`GAPS:`/`ASSUMPTIONS:` for any entry involving a real decision;
     summary-only for mechanical edits. Why: this is what lets a cold-start
     agent resume the work from the log alone.
   - **When to report**: after code changes, and by default before merging
     the current branch into its base if the branch has unreported changes —
     don't wait to be asked. Why: reports are the per-branch decision record;
     merging without one loses the branch's rationale once it's squashed.
   If no memory system is available, skip this step silently — the `CLAUDE.md`
   block from step 7 is the fallback that keeps the policy discoverable.

Report the created tree and the detected profile summary.
