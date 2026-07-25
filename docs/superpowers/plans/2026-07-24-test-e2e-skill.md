# test-e2e Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a project skill, `/test-e2e`, to the `monitor-tools` repo that runs the manual "clone a project, install monitor, dogfood it" drill 3-wide in parallel — one project per language (Python/Node/Go-or-docs), one companion-install level per project (none/some/all) — and produces a synthesized HTML comparison report.

**Architecture:** A single `SKILL.md` file at `.claude/skills/test-e2e/` containing runtime instructions (no code to execute — this is a prompt document the invoking agent follows). It tells the agent to: WebSearch 3 fresh repos, spawn 3 parallel worktree-isolated subagents with a filled-in template prompt, wait for completion, read back each worktree's `monitor/` artifacts, and synthesize one HTML report via `ui-ux-pro-max`.

**Tech Stack:** Markdown (SKILL.md), no new code/scripts. Relies on existing repo tooling: `install-monitor.sh`, the `Agent` tool's `isolation: "worktree"`, `WebSearch`, `ui-ux-pro-max` skill, `SendUserFile`.

## Global Constraints

- Skill directory/frontmatter name: `test-e2e` (letters/numbers/hyphens only — no colon; colon syntax is reserved for plugin `plugin:command` namespacing, not usable here).
- Invoked as `/test-e2e`, same convention as the existing `.claude/skills/create-readme/SKILL.md`.
- Repo candidates are found fresh via `WebSearch` every run — never hardcoded.
- Each of the 3 subagents gets `isolation: "worktree"` (full git worktree of `monitor-tools`), `run_in_background: true`, and all 3 are dispatched in one message so they run in parallel.
- Companion install sources (confirmed with the user, already used once this session against `example/`):
  - `ui-ux-pro-max` → marketplace `nextlevelbuilder/ui-ux-pro-max-skill`, plugin `ui-ux-pro-max`
  - `superpowers` → marketplace `anthropics/claude-plugins-official`, plugin `superpowers`
  - `openwiki` → marketplace `SoulKyu/openwiki-cc`, plugin `openwiki`
  - `find-skills` → `npx skills add vercel-labs/skills@find-skills` (no `-g`)
  - `copywriting` → `npx skills add coreyhaines31/marketingskills@copywriting` (no `-g`)
  - `graphify` → `pip install graphifyy && graphify install` (global only — no project-scoped path exists)
- Combined report path: `temp/test-e2e-runs/<YYYY-MM-DD>.html`, written in the **main** working tree (not any worktree), gitignored (`.gitignore` already covers `temp/` and `examples/` as of the prior commit on this branch).
- This skill is project-local to `monitor-tools` — never copied into `plugins/monitor/`.

---

### Task 1: Write the `test-e2e` skill

**Files:**
- Create: `.claude/skills/test-e2e/SKILL.md`

**Interfaces:**
- Produces: a skill invocable as `/test-e2e` with no arguments. Nothing downstream consumes this — it's a leaf deliverable.

- [ ] **Step 1: Write `.claude/skills/test-e2e/SKILL.md`**

```markdown
---
name: test-e2e
description: Runs a 3-way parallel dogfood drill of the monitor plugin — clones a fresh small Python, Node, and Go-or-docs project, installs monitor into each with a different companion-skill level (none/some/all), has an isolated subagent use each project like a real developer, then synthesizes one HTML comparison report. Use when asked to test monitor end-to-end, run the testing drill, or dogfood the monitor plugin.
---

# test-e2e

Parallel end-to-end dogfood drill for the `monitor` plugin, 3 projects wide.
Tests the plugin's actual behavior against real projects — not a unit test,
a real usage drill, same spirit as the manual drills already done this
session but run 3-at-once with varying companion-install levels.

## Flow

1. **Find 3 fresh test repos.** Use `WebSearch` (never a hardcoded list) to
   find one small, real, currently-existing repo for each:
   - a small Python CLI project
   - a small Node/JS CLI project
   - a small Go project, or a small docs-only project if no small Go repo
     turns up
   Prefer repos with a handful of files, not sprawling ones — small enough
   that a subagent can orient in one read pass.

2. **Spawn 3 subagents in parallel — one message, three `Agent` calls,**
   each with `subagent_type: "general-purpose"`, `isolation: "worktree"`,
   `run_in_background: true`. Each subagent gets the prompt template below
   with its own `{repo_url}`, `{project_dir}` (always `examples/<slug>`,
   `<slug>` derived from the repo name), and `{companion_level}`:

   | Agent | Language | companion_level |
   |---|---|---|
   | A | Python repo | `none` |
   | B | Node repo | `some` (install `superpowers` + `graphify` only) |
   | C | Go-or-docs repo | `all` (install all 6) |

   **Subagent prompt template:**

   ```
   You're doing a real end-to-end usage test of a Claude Code plugin called
   "monitor" inside a fresh clone of a small open-source project. Work only
   inside this worktree — don't touch anything outside it.

   1. Clone {repo_url} into {project_dir} (relative to the repo root you're
      in), then cd into it.
   2. From the repo root (one level up from {project_dir}), run:
      ./install-monitor.sh {project_dir}
   3. Companion skill level for this run: {companion_level}.
      - If "none": skip this step entirely.
      - If "some": install superpowers and graphify only, project-scoped:
        - superpowers: merge into {project_dir}/.claude/settings.json —
          "extraKnownMarketplaces": {"claude-plugins-official": {"source":
          {"source": "github", "repo": "anthropics/claude-plugins-official"}}},
          "enabledPlugins": {"superpowers@claude-plugins-official": true}
        - graphify: pip install graphifyy && graphify install (global —
          only needs doing once per machine, safe to re-run)
      - If "all": install all 6 companions, project-scoped where a
        project-scoped path exists:
        - ui-ux-pro-max: marketplace nextlevelbuilder/ui-ux-pro-max-skill,
          plugin ui-ux-pro-max — same extraKnownMarketplaces/enabledPlugins
          pattern as above
        - superpowers: as in "some" above
        - openwiki: marketplace SoulKyu/openwiki-cc, plugin openwiki — same
          pattern
        - find-skills: npx skills add vercel-labs/skills@find-skills (run
          from inside {project_dir}, no -g flag)
        - copywriting: npx skills add coreyhaines31/marketingskills@copywriting
          (same, no -g)
        - graphify: pip install graphifyy && graphify install (global)
   4. Now act like a real developer who just opened this project, with no
      special knowledge of monitor beyond what you discover in the project
      itself. Look around, pick several small real things worth doing (a
      bug fix, a missing test, a docs fix, dead code removal — your call),
      and do them. Follow whatever CLAUDE.md/AGENTS.md tells you once
      /monitor:init has been run — don't be told monitor's command names
      directly, discover them the way a real user would.
   5. Do at least 5 separate rounds of small changes so there's real log
      and report volume to inspect afterward.
   6. Report back in plain language: what you changed, whether/how you
      used monitor (which commands, how many times), and anything that
      looked broken, confusing, inconsistent, or undocumented — including
      anything about the companion-install step if companion_level wasn't
      "none".
   ```

3. **Wait for all 3 to complete** (event-driven completion notifications —
   never poll or sleep-loop for this).

4. **Read back real data from each worktree**, not just each subagent's
   self-report: for each of the 3, open `{project_dir}/monitor/profile.json`,
   `{project_dir}/monitor/logs/operations.mtr`, and list
   `{project_dir}/monitor/reports/*.html`. Count log entries and reports,
   and spot-check that `--details` fields look like real content (not
   corrupted, not placeholder text). This is the same
   verify-before-trusting-a-subagent's-claims practice used in every manual
   drill so far — don't just relay what the subagent said happened.

5. **Synthesize one combined HTML report.** Invoke the `ui-ux-pro-max`
   skill, then write a single self-contained HTML file to
   `temp/test-e2e-runs/<YYYY-MM-DD>.html` (today's date, in the **main**
   working tree — not inside any worktree) covering, per project: repo
   name/language, companion level, number of commits/changes made, log
   entry count, report count, and a short findings list (bugs,
   inconsistencies, compliance gaps) drawn from both the subagent's report
   and your own spot-check in step 4.

6. **Send the report** to the user with `SendUserFile`, `status: "proactive"`.

## Notes

- This skill tests the `monitor` plugin; it is not part of it and is never
  copied into `plugins/monitor/`.
- Repos are found fresh every run — don't reuse or hardcode candidates from
  a previous run.
- Each subagent's worktree is disposable — nothing under it needs to
  survive after the report is written, but nothing in this flow deletes it
  either; that's a manual cleanup call for whoever ran it.
```

- [ ] **Step 2: Verify frontmatter is well-formed**

Run: `python3 -c "import yaml,sys; d=yaml.safe_load(open('.claude/skills/test-e2e/SKILL.md').read().split('---')[1]); assert d['name']=='test-e2e'; assert d['description'].startswith('Runs a 3-way'); print('ok:', d['name'])"`

Expected: `ok: test-e2e` (if `yaml` isn't installed, `pip install pyyaml` first, or just visually confirm the two `---`-delimited frontmatter lines parse as `name: test-e2e` / `description: ...`).

- [ ] **Step 3: Confirm the skill loads**

Run `/reload-skills` in the session (or start a fresh one) and confirm `test-e2e` appears in the available-skills listing, description intact.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/test-e2e/SKILL.md
git commit -m "$(cat <<'EOF'
feat: add test-e2e skill for parallel monitor dogfooding

Runs the manual clone+install+dogfood drill 3-wide across
Python/Node/Go-or-docs projects, one companion-install level each
(none/some/all), synthesized into one HTML comparison report.
EOF
)"
```

---

### Task 2: Dry-run the skill for real (this skill's own test)

This is the "verification" the design doc calls for — an orchestration skill
like this has no rationalization to bulletproof (no RED/GREEN pressure-test
methodology applies), so its test is a live invocation, same bar as every
manual drill already run this session.

**Files:** none created — this task exercises Task 1's output.

**Interfaces:**
- Consumes: `.claude/skills/test-e2e/SKILL.md` from Task 1.

- [ ] **Step 1: Invoke `/test-e2e`**

Run the skill for real in this session (or a fresh one). Confirm out loud,
before proceeding, that 3 `Agent` calls were dispatched in the same message
with `isolation: "worktree"` and `run_in_background: true` — if they went
out sequentially or without worktree isolation, stop and fix Task 1's
`SKILL.md` wording (the instruction to dispatch in "one message" may need to
be stated more forcefully), then re-run this step.

- [ ] **Step 2: Wait for all 3 subagents to report completion**

No polling — this is event-driven. If one subagent stalls past what's
reasonable for a small-repo clone + a handful of edits, that's a real finding
to note in the drill report, not something to work around.

- [ ] **Step 3: Verify each worktree actually has real monitor data**

For each of the 3 worktrees, confirm:
- `examples/<slug>/monitor/profile.json` exists and has a non-generic
  `project.name`
- `examples/<slug>/monitor/logs/operations.mtr` has 5+ entries with
  non-empty `summary`/`status` fields (not corrupted, not placeholder)
- `examples/<slug>/monitor/reports/` has at least the `template.html` and,
  for projects where real code changed, at least one dated report file

If any of these come back empty/placeholder-only, that's a bug in either
the `SKILL.md` prompt template (Task 1) or in `monitor` itself — note which,
fix the template if it's a wording gap, and re-run from Step 1.

- [ ] **Step 4: Verify the combined HTML report**

Confirm `temp/test-e2e-runs/<today's-date>.html` exists in the **main**
working tree (not a worktree), opens as valid self-contained HTML, and its
per-project figures (log/report counts, companion level) match what you
found in Step 3 by hand — not just numbers the subagent claimed. Confirm
`SendUserFile` was actually called with this path.

- [ ] **Step 5: Report the dry-run outcome**

Summarize to the user: did all 3 subagents complete, did each worktree get
real monitor data, did the combined report render with real figures, and
list any findings the drill itself surfaced about `monitor` (bugs,
inconsistencies) separately from findings about the `test-e2e` skill
template itself (wording gaps, missing detail).

---

### Task 3: Finish the branch

- [ ] Announce: "I'm using the finishing-a-development-branch skill to
  complete this work."
- **REQUIRED SUB-SKILL:** Use `superpowers:finishing-a-development-branch`
  to verify the branch state and present merge/PR/cleanup options.
