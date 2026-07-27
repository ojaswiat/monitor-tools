# test-e2e Skill Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update `.claude/skills/test-e2e/SKILL.md` so dogfood drills exercise the tasks feature and the pending-state hook gate, and self-correct when a subagent's worktree is cut from a stale branch state.

**Architecture:** This is a single Markdown prompt-template file, not application code — the "implementation" is careful prose editing of the subagent dispatch template and the orchestrator steps around it. No pytest-equivalent exists for a skill file; validation is manual re-reading for internal consistency, matching how every prior edit to this file (visible in its own git log) was done.

**Tech Stack:** Markdown (Claude Code skill spec format — YAML frontmatter + prose). No code, no dependencies.

## Global Constraints

- This skill tests the `monitor` plugin; it stays under `.claude/skills/test-e2e/` and is never copied into `plugins/monitor/`.
- Repos are found fresh every run (`WebSearch`, never a hardcoded list) — untouched by this plan.
- The containment rules (no `find`/`ls`/`grep` rooted outside the project, for both orchestrator and subagents) — untouched by this plan.
- The 3-language/3-companion-level matrix (Python/none, Node/some, Go-or-docs/all) — untouched by this plan.
- No test suite exists in this repo (per `CLAUDE.md`) — every "test" step below is a manual read-through of the edited file for correctness, not a command to run.
- All work happens on branch `improve/test-e2e` (already checked out, forked from `dev`).

---

### Task 1: Update the subagent template and orchestrator steps in SKILL.md

**Files:**
- Modify: `.claude/skills/test-e2e/SKILL.md`

**Interfaces:**
- N/A — this is a documentation file with no code interfaces. The "interface" is the exact prose contract between the orchestrator's steps and what it tells each dispatched subagent to do.

- [ ] **Step 1: Add the version-capture line to skill step 2 (before the subagent prompt template)**

In `SKILL.md`, immediately after the existing sentence that ends "...don't resend the whole batch or swap in a different repo/level for it." (currently the paragraph right after the retry-on-classifier-denial note, before "**Subagent prompt template:**"), insert:

```markdown
   Before writing each subagent's prompt, capture the current plugin
   version so subagents can detect if the branch moves under them between
   dispatch and worktree creation:
   ```bash
   grep '"version"' plugins/monitor/.claude-plugin/plugin.json
   ```
   Pass the printed value into every subagent's prompt as `{expected_version}`.
```

- [ ] **Step 2: Add Step 0 to the subagent prompt template — stale-worktree self-check**

Inside the fenced ` ```  ` code block that IS the subagent prompt template, immediately before the current "1. Clone {repo_url} into..." line, insert a new numbered step 0 and renumber nothing else (the existing steps keep their 1-6 numbers; this is deliberately "0" since it runs before cloning, mirroring how the existing template already numbers from 1):

```markdown
   0. Before anything else, check whether this repo's branch has moved
      since you were dispatched: run
      `grep '"version"' plugins/monitor/.claude-plugin/plugin.json` from
      the repo root you're in. If the printed version does not match
      `{expected_version}`, the branch advanced after dispatch — run
      `git merge <base-branch>` (substitute the actual branch name this
      drill is running on, e.g. `dev` or the feature branch) right now,
      before proceeding to step 1. If it matches, proceed directly to
      step 1. State in your final report which case happened.
   ```

- [ ] **Step 3: Add the tasks-feature and pending-hook steps to the subagent prompt template, and renumber the report step**

The template's steps 1-5 (clone, install, companion level, act like a developer, 5 rounds) stay exactly as they are today. Delete the existing step 6 ("Report back in plain language...") entirely — it is replaced below by the new step 8. Insert two new steps (6 and 7) after step 5, then re-add the report step as step 8. The final subagent template step order must read exactly:

```
   1. Clone ...
   2. From the repo root ...
   3. Companion skill level ...
   4. Now act like a real developer ...
   5. Do at least 5 separate rounds ...
   6. As part of (not separate from) those 5 rounds, use the project's
      task-tracking commands ...
   7. Somewhere in those same 5 rounds, make at least one real commit
      without logging it first, then simulate what the two installed
      pending-state hooks would do (you cannot trigger Claude Code's real
      PostToolUse/UserPromptSubmit hook dispatch from inside this
      subagent — there's no live interactive session here, so this is a
      deliberate simulation, not the real thing): pipe the same JSON a
      real hook call would receive directly into
      `{project_dir}/monitor/scripts/pending.py hook-post-tool-use` and
      then `hook-user-prompt-submit`. Verify the unlogged commit shows up
      in `monitor/.pending.json`, the user-prompt-submit simulation
      produces a sensible warning message, and running the project's
      actual log command afterward clears the matching pending entry.
   8. Report back in plain language: what you changed, whether/how you
      used monitor (which commands, how many times), and anything that
      looked broken, confusing, inconsistent, or undocumented — including
      anything about the companion-install step if companion_level wasn't
      "none". Your worktree will likely be gone by the time this is read,
      so paste the real evidence inline rather than describing it: the
      final log-entry count and report count, one full `--details` block
      copied verbatim from `operations.mtr` (not paraphrased) so it can be
      checked for real content vs. placeholder text, the final task count
      in `monitor/tasks/tasks.mtr`, one full task's self-reported metrics
      pasted verbatim, and the pending-hook test outcome from step 7 —
      pass or fail, with the warning message text pasted verbatim.
```

Apply this as the authoritative final text for steps 1 through 8 of the subagent prompt template (replacing steps 1-6 as they exist today with this exact 1-8 sequence — step 0 from Step 2 above stays where it is, before step 1).

- [ ] **Step 5: Update skill step 4 (orchestrator verification) to mention the new evidence**

The existing skill step 4 reads:
```markdown
4. **Verify, don't just relay.** Try reading each worktree directly first —
   `{project_dir}/monitor/profile.json`, `logs/operations.mtr`, and
   `reports/*.html` — and cross-check counts and `--details` content
   against what the subagent claimed. In every run so far the worktree was
   already gone by this point (auto-pruned by the harness once the
   subagent stopped), so treat that as the expected case, not an error:
   fall back to checking the verbatim log-entry count, report count, and
   `--details` excerpt each subagent was told to paste into its own report
   (step 6 above) for internal consistency and real content, same
   verify-before-trusting-a-subagent's-claims practice as any manual
   drill — just against pasted evidence instead of live files.
```
Replace the two references to "step 6 above" with "step 8 above" (the report step's new number), and add task/hook evidence to the direct-read attempt and the fallback:
```markdown
4. **Verify, don't just relay.** Try reading each worktree directly first —
   `{project_dir}/monitor/profile.json`, `logs/operations.mtr`,
   `reports/*.html`, `tasks/tasks.mtr`, and `.pending.json` — and cross-check
   counts and `--details` content against what the subagent claimed. In
   every run so far the worktree was already gone by this point
   (auto-pruned by the harness once the subagent stopped), so treat that as
   the expected case, not an error: fall back to checking the verbatim
   log-entry count, report count, task count, one task's metrics, and the
   pending-hook pass/fail each subagent was told to paste into its own
   report (step 8 above) for internal consistency and real content, same
   verify-before-trusting-a-subagent's-claims practice as any manual
   drill — just against pasted evidence instead of live files.
```

- [ ] **Step 6: Update skill step 5 (report synthesis) to add the two new columns**

The existing skill step 5 reads:
```markdown
5. **Synthesize one combined HTML report.** Invoke the `ui-ux-pro-max`
   skill, then write a single self-contained HTML file to
   `temp/test-e2e-runs/<YYYY-MM-DD>.html` (today's date, in the **main**
   working tree — not inside any worktree). If a file for today already
   exists (a second run same day), append `-round-N` rather than
   overwriting it. Cover, per project: repo
   name/language, companion level, number of commits/changes made, log
   entry count, report count, and a short findings list (bugs,
   inconsistencies, compliance gaps) drawn from both the subagent's report
   and your own spot-check in step 4.
```
Replace the "Cover, per project:" sentence with:
```markdown
   Cover, per project: repo name/language, companion level, number of
   commits/changes made, log entry count, report count, task count, and
   hook-test result (pass/fail, with the one-line reason on fail) — plus a
   short findings list (bugs, inconsistencies, compliance gaps) drawn from
   both the subagent's report and your own spot-check in step 4.
```

- [ ] **Step 7: Re-read the whole file for internal consistency (this task's only "test")**

Open `.claude/skills/test-e2e/SKILL.md` and confirm, reading top to bottom:
- The subagent prompt template's steps are numbered 0, 1, 2, 3, 4, 5, 6, 7, 8 with no gaps or duplicates, and step 8 is the final step (the report step).
- Every place that said "step 6" referring to the report step now says "step 8".
- `{expected_version}` is introduced in skill step 2 (before the template) and used inside the template's step 0 — no undefined placeholder.
- Skill step 4 and step 5's prose both mention tasks and hooks alongside logs/reports.
- No leftover reference to the old step numbering anywhere in the file (search for "step 6" — every remaining instance must refer to the report step, now step 8; if any other "step 6" reference exists pointing at the old content, fix it).

If any inconsistency is found, fix it directly in the file before moving on — this is a single-file documentation change, so "test" here means the file reads correctly end-to-end, not a passing command.

- [ ] **Step 8: Commit**

```bash
cd /Users/ojaswi/Projects/monitor-tools
git add .claude/skills/test-e2e/SKILL.md
git commit -m "feat(test-e2e): cover tasks feature and pending-hook gate, fix stale-worktree dispatch"
```

---

## Self-Review Notes

**Spec coverage:** all four spec changes map into this single task's steps — stale-worktree fix (Steps 1-2), tasks-feature coverage (Step 3's new step 6), pending-hook coverage (Step 4's new step 7), report synthesis update (Step 6). The spec's non-goals (repo-finding method, companion matrix, containment rules, worktree cleanup notes) are untouched — no step in this plan edits those sections.

**Placeholder scan:** every step gives the exact replacement text to write, not a description of what to write. No "TBD"/"add appropriate", no forward references to undefined content.

**Type/number consistency:** the subagent template's step numbering is spelled out fully and exactly once, as the authoritative final sequence (Step 4), so there's no ambiguity between the incremental edits in Steps 2-4 and the end state — an implementer should treat Step 4's full 1-8 listing as the source of truth for the template body, and Steps 1, 5, 6 as the edits around it.
