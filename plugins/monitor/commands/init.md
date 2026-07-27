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
   (`profile.py` only fills in the project's directory name — monitor's jobs
   are log, report, and track tasks; it never detects language/build/test
   commands or otherwise inspects the project. For real project orientation,
   use a companion skill like `graphify` instead.)
4. Generate project-specific assets from the profile:
   `python3 monitor/scripts/render_report.py` (writes `reports/template.html`,
   `reports/index.html`, `index.html`, and `tasks/index.html` — the Reports
   index is scanned fresh from `reports/*.html`, no manifest file) and
   `python3 monitor/scripts/render_logs.py` (creates an empty-state Logs
   page if there is no log yet).
5. Probe companion skills (graphify, superpowers, openwiki, ui-ux-pro-max,
   find-skills, copywriting) via `.claude/settings.json` enabledPlugins and the
   skills folder. Write `monitor/usage.md`: for each, PRESENT/ABSENT and how
   monitor uses it here (from the SKILL.md companion table). For absent
   high-fit skills, recommend them and offer to install now — installation
   stays user-gated, never automatic.

   **Installing companions (optional, only on explicit user approval):**
   Ask once, listing which absent skills you'd install and how, before
   running anything. Prefer project-scoped install so every clone of the
   repo gets the same companions, not just this machine:
   - **ui-ux-pro-max / superpowers / openwiki** (plugins): add the
     marketplace + enable the plugin in the project's `.claude/settings.json`
     — merge in (don't clobber existing keys):
     ```json
     {
       "extraKnownMarketplaces": {
         "ui-ux-pro-max-skill": {"source": {"source": "github", "repo": "nextlevelbuilder/ui-ux-pro-max-skill"}},
         "claude-plugins-official": {"source": {"source": "github", "repo": "anthropics/claude-plugins-official"}},
         "openwiki-cc": {"source": {"source": "github", "repo": "SoulKyu/openwiki-cc"}}
       },
       "enabledPlugins": {
         "ui-ux-pro-max@ui-ux-pro-max-skill": true,
         "superpowers@claude-plugins-official": true,
         "openwiki@openwiki-cc": true
       }
     }
     ```
     Only add entries for skills the user approved; leave others out.
   - **find-skills / copywriting** (skills-CLI packages): install
     project-scoped by omitting `-g` (lands under the project, committed with
     the repo, shared with every clone):
     ```bash
     npx skills add vercel-labs/skills@find-skills
     npx skills add coreyhaines31/marketingskills@copywriting
     ```
   - **graphify**: no project-scoped install exists — its own installer
     always targets `~/.claude/skills/graphify`, so this one is necessarily
     global, on approval:
     ```bash
     pip install graphifyy && graphify install
     ```
   After installing, re-probe and update `monitor/usage.md` to PRESENT for
   whatever was just installed.
6. Ensure `.gitignore` contains `monitor/scripts/__pycache__/`.
7. **Install the pending-state hooks.** Merge these two entries into the
   project's `.claude/settings.json` under a top-level `"hooks"` key
   (merge in — don't clobber any existing `hooks` entries for other tools):
   ```json
   {
     "hooks": {
       "PostToolUse": [
         {
           "matcher": "Bash",
           "hooks": [
             {"type": "command",
              "command": "python3 \"$CLAUDE_PROJECT_DIR/monitor/scripts/pending.py\" --project-root \"$CLAUDE_PROJECT_DIR\" hook-post-tool-use",
              "timeout": 10}
           ]
         }
       ],
       "UserPromptSubmit": [
         {
           "hooks": [
             {"type": "command",
              "command": "python3 \"$CLAUDE_PROJECT_DIR/monitor/scripts/pending.py\" --project-root \"$CLAUDE_PROJECT_DIR\" hook-user-prompt-submit",
              "timeout": 10}
           ]
         }
       ]
     }
   }
   ```
   A command hook is a single shell string — there is no `args` array. Note
   `--project-root` comes *before* the subcommand: `pending.py` registers it
   as a top-level argument, so argparse rejects it if it trails the
   subcommand. `UserPromptSubmit` carries **no** `matcher` key — matchers scope
   a hook to a tool, and that event has no tool (only `PostToolUse` is
   tool-scoped, on `Bash`). The `timeout` bounds git subprocess calls in a
   large repo so a slow hook fails fast instead of stalling the turn.
   These are silent unless something is actually pending — see "Pending-state
   enforcement" in `SKILL.md`.
8. Add or update a **monitor** section in **both** `CLAUDE.md` and `AGENTS.md`
   at the project root (create whichever file doesn't exist — different
   agents/tools read one or the other, so both get the same block). Write it
   between `<!-- monitor:start -->` / `<!-- monitor:end -->` markers in each
   file so re-running `/monitor:init` or `/monitor:update` replaces the block
   instead of duplicating it. Same content in both files:
   ```markdown
   <!-- monitor:start -->
   ## monitor — operations log + reports

   This project has **monitor** installed: a local logging/reporting workflow.
   It keeps a project-local `monitor/` folder — a Dashboard linking a **Reports**
   page (one self-contained HTML report per task/change), a **Logs** page
   (rendered from `monitor/logs/operations.mtr`, a locked-schema text log), and a
   **Tasks** page (lifecycle-tracked units of work, rendered from
   `monitor/tasks/tasks.mtr`). Rules for using it live in
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
   | `/monitor:search <query>` | Search the operations log by keyword; plain-text output. |
   | `/monitor:update` | Re-detect + additively reconcile the profile, refresh assets. |
   | `/monitor:task-start "<title>"` | Start a lifecycle-tracked task; prints its `task_id`. |
   | `/monitor:task-update <id>` | Append a status/metrics update to an open task. |
   | `/monitor:task-close <id>` | Close a task with a terminal status (success/failed/cancelled). |
   | `/monitor:clean-logs <N>` | Delete the oldest N log entries; re-render Logs. |
   | `/monitor:clean-reports <N>` | Delete the oldest N reports; re-render Reports + Dashboard. |
   | `/monitor:clean-tasks <N>` | Delete the oldest N tasks (all their events); re-render Tasks + Dashboard. |

   **Rules:**
   - Every command except `/monitor:init` requires `monitor/profile.json` to
     exist — it fails fast otherwise. Run init first if it's missing.
   - Never hand-edit `monitor/logs/operations.mtr` — always go through
     `logger.py` (via `/monitor:log` or `/monitor:record`); hand-edits desync
     the log from the rendered Logs page.
   - Reports are immutable snapshots — never rewrite an old report when the
     template changes; only new reports pick up new sections.
   - A task is a separate tracked entity, not a field on a log entry — track
     it with `/monitor:task-start`/`task-update`/`task-close` (never hand-edit
     `monitor/tasks/tasks.mtr`), and cross-reference it from log entries with
     `logger.py --task-id <id>`.
   - `monitor/profile.json` evolves additively only — `/monitor:update` adds
     detected fields, never removes or renames existing ones.
   - After a commit, merge, or rebase, a `[Warn!] Monitor: Pending logs and
     report...` line may appear at the start of a turn. That is monitor's
     pending-state gate reporting unlogged/unreported work, not a bug —
     answer Y to record it now, or N to defer.
   - **Never record development history, version changelogs, or reasoning
     leakage in any user-facing documentation** (READMEs, skill files,
     this project's own `CLAUDE.md`/`AGENTS.md`, generated docs). Write
     every doc as clean, state-only content describing *current* behavior —
     never "this used to work differently" or "version X did Y before it
     was removed." Version history belongs in git commits only. The
     verbose *why* belongs in monitor's logs/reports, not in shipped docs.
   <!-- monitor:end -->
   ```
9. **If a persistent memory system is available to you** (a memory directory
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
   If no memory system is available, skip this step silently — the
   `CLAUDE.md`/`AGENTS.md` blocks from step 8 are the fallback that keeps the
   policy discoverable.

Report the created tree and the detected profile summary.
