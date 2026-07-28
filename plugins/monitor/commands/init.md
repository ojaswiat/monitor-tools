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
           "matcher": "Bash|Write",
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
   tool-scoped, on `Bash|Write`: `Bash` for detecting commits/merges/rebases,
   `Write` for detecting a plan/spec file with no task tracking the work).
   The `timeout` bounds git subprocess calls in a large repo so a slow hook
   fails fast instead of stalling the turn. These are silent unless
   something is actually pending — see "Pending-state enforcement" in
   `SKILL.md`.
8. Add or update a **monitor** section in **both** `CLAUDE.md` and `AGENTS.md`
   at the project root (create whichever file doesn't exist — different
   agents/tools read one or the other, so both get the same block). Write it
   between `<!-- monitor:start -->` / `<!-- monitor:end -->` markers in each
   file so re-running `/monitor:init` or `/monitor:update` replaces the block
   instead of duplicating it. Same content in both files:
   ```markdown
   <!-- monitor:start -->
   ## monitor — operations log, tasks, and reports

   This project has **monitor** installed: a local logging/reporting workflow.
   It keeps a project-local `monitor/` folder — a Dashboard linking a **Reports**
   page (one self-contained HTML report per task/change), a **Logs** page
   (rendered from `monitor/logs/operations.mtr`, a locked-schema text log), and a
   **Tasks** page (lifecycle-tracked units of work, rendered from
   `monitor/tasks/tasks.mtr`). Rules for using it live in
   the skill at `SKILL.md` (or `$CLAUDE_PLUGIN_ROOT/skills/monitor/SKILL.md`
   when installed as a plugin) — read it before running any command below.

   The three tracked entities have a clear split: **logs** are the continuous
   record (every operation, including the start and end of bigger ones);
   **tasks** mark only the start and close of a multi-step unit of work, not
   the steps in between; **reports** are a one-per-branch summary snapshot.

   ### Logging

   **Use case:** the continuous audit trail. Every state-changing operation
   gets an entry — this is what lets a different agent (or a later session)
   resume cold without re-deriving what happened or why.

   **How to use (hard rule — not optional, no exceptions):**
   - Run `/monitor:log` or `/monitor:record` after every state-changing
     operation, including small ones (one file edit, one command run, one
     config tweak). This is default behavior, not something to wait for
     permission on — the operation itself is the trigger, and the user
     staying silent about monitor is not a signal to skip it. A tight
     edit+build+commit can be one entry, but don't skip logging just
     because the change was small.
   - On failure, log it anyway with `status=failure` and the real error —
     don't skip logging just because the operation didn't succeed.
   - For real decisions, log the reasoning, not just the outcome. In
     `--details`, capture (whichever apply) `DECISION:` what was chosen,
     `WHY:` alternatives considered and rejected, `ARCHITECTURE:` what
     structurally changed, `NEXT:` the immediate next step, `GAPS:` known
     issues/TODOs, `ASSUMPTIONS:` anything unverified. A trivial mechanical
     edit just needs `--summary`, no `--details`. Reports pull their
     **Decisions & Rationale** and **Gaps & Assumptions** sections straight
     from these fields — see `SKILL.md` for the full convention.
   - Only an explicit user instruction to skip logging for a specific
     action overrides this rule — and that override applies to the single
     action it was given for, not the rest of the session.

   ### Task Tracking

   **Use case:** marks only the initial and final stages of a multi-step
   unit of work — the boundary, not the in-between (logging already covers
   that, cross-referenced back to the task via `--task-id`). Distinct from
   logging: logs are continuous, tasks are start/close bookends around a
   unit of work large enough to need one.

   **How to use (hard rule — not optional, no exceptions):**
   - Start a task (`/monitor:task-start "<title>"`) before beginning any
     unit of work with more than one step, update it
     (`/monitor:task-update <id>`) as status changes, and close it
     (`/monitor:task-close <id>`) on completion or failure — same hard-rule
     treatment as logging, not something to ask about first.
   - Only an explicit user instruction to skip task-tracking for a specific
     action overrides this rule — and that override applies to the single
     action it was given for, not the rest of the session.
   - monitor also nudges when it notices a plan/spec markdown file get
     written (any `plans/` or `specs/` directory) with no task currently
     open — a `[Warn!] Monitor: no task tracked for recent plan/spec work`
     line, informational and non-blocking. It is a heuristic, not a
     guarantee: it does not fire for work that never touches such a file,
     and does not know whether an already-open task actually covers new
     work — start one whenever real multi-step work begins, don't wait for
     the nudge.

   ### Reporting

   **Use case:** one branch-level summary snapshot — decisions, rationale,
   files touched, gaps — generated before merge so a reviewer (human or
   agent) can read the whole branch's reasoning in one place instead of
   piecing it together from commits.

   **How to use (default judgment — apply as usual, not forced every time):**
   - Generate a report before every merge if the branch has code changes not
     yet covered by one — do this by default when asked to merge, don't wait
     to be asked for a report separately.
   - After code changes generally, write a report with `/monitor:report` (or
     via `/monitor:record`) — never report a discussion or doc-only tweak.
   - Reports render an HTML page and cost more to generate than a log entry
     — apply judgment on *when* one is warranted (per the two rules above),
     rather than authoring one for every single logged operation.

   ### Search

   **Use case:** find past decisions and context across logs, reports, and
   tasks without reading files by hand — the mechanism that makes the
   audit trail actually useful instead of just accumulating.

   **How to use:**
   - `/monitor:search <query>` — case-insensitive substring search.
     `--scope logs|reports|tasks|all` picks the source (default `all`,
     grouped by source in the output); `--branch`/`--status`/`--level`
     filter log matches.

   ### Cleanup

   **Use case:** prune old entries once the Dashboard grows long — logs,
   reports, and tasks are each pruned independently, oldest first.

   **How to use:**
   - `/monitor:clean-logs <N>` — delete the oldest N log entries.
   - `/monitor:clean-reports <N>` — delete the oldest N reports.
   - `/monitor:clean-tasks <N>` — delete the oldest N tasks (all their
     events).

   ### Status

   **Use case:** a quick "what's going on" snapshot — open tasks, recent
   activity, pending items, next steps — without reading logs/tasks/git by
   hand. Chat-only: it never writes a report, dashboard entry, or any other
   file.

   **How to use:**
   - `/monitor:status` — prints straight to chat. Every fact comes from
     existing data (open tasks, the last few log entries, `NEXT:`/`GAPS:`/
     `ASSUMPTIONS:` fields already recorded in those entries, the
     pending-state gate, and recent git history) — nothing is inferred or
     guessed.

   ### Commands

   | Command | Does |
   |---|---|
   | `/monitor:init` | First-time setup (idempotent). Run once per project. |
   | `/monitor:log` | Append one operation entry to the log. |
   | `/monitor:report` | Author one HTML report + rebuild the Reports index. |
   | `/monitor:record` | Log, and if code changed, report — in one step. |
   | `/monitor:search <query>` | Search logs, reports, and tasks by keyword; plain-text output. |
   | `/monitor:status` | Show open tasks, recent activity, pending items, and next steps directly in chat. Never writes a file. |
   | `/monitor:update` | Re-detect + additively reconcile the profile, refresh assets. |
   | `/monitor:task-start "<title>"` | Start a lifecycle-tracked task; prints its `task_id`. |
   | `/monitor:task-update <id>` | Append a status/metrics update to an open task. |
   | `/monitor:task-close <id>` | Close a task with a terminal status (success/failed/cancelled). |
   | `/monitor:clean-logs <N>` | Delete the oldest N log entries; re-render Logs. |
   | `/monitor:clean-reports <N>` | Delete the oldest N reports; re-render Reports + Dashboard. |
   | `/monitor:clean-tasks <N>` | Delete the oldest N tasks (all their events); re-render Tasks + Dashboard. |

   ### Rules

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
     report...` line may appear at the start of a turn — monitor's
     pending-state gate reporting unlogged/unreported work, not a bug.
     Answer Y to record it now, or N to defer. A separate
     `[Warn!] Monitor: no task tracked for recent plan/spec work` line (see
     Task Tracking above) works the same way but is purely informational,
     never a Y/N question.
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
