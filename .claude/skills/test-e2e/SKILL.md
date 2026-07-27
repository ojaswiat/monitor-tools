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
   that a subagent can orient in one read pass. WebSearch results go stale
   or hallucinate paths (hit this live: a search-recommended repo didn't
   exist under the given owner) — the subagent template's step 1 below
   makes cloning-and-verifying the subagent's own job, so a bad candidate
   fails fast as a clear report instead of the subagent improvising a
   replacement repo mid-task.

2. **Spawn 3 subagents in parallel — one message, three `Agent` calls,**
   each with `subagent_type: "general-purpose"`, `isolation: "worktree"`,
   `run_in_background: true`. Each subagent gets the prompt template below
   with its own `{repo_url}`, `{project_dir}` (always `examples/<slug>`,
   `<slug>` derived from the repo name), and `{companion_level}`:

   | Agent | Language | companion_level |
   |---|---|---|
   | A | Python repo | `none` |
   | B | Node repo | `some` (install `superpowers` only — see step 3) |
   | C | Go-or-docs repo | `all` (install all 6) |

   If any of the 3 `Agent` calls comes back denied by the auto-mode
   classifier (seen in practice — it's launch-time flakiness, not a
   problem with the request), retry that one call alone; don't resend the
   whole batch or swap in a different repo/level for it.

   Before writing each subagent's prompt, capture the current plugin
   version so subagents can detect if the branch moves under them between
   dispatch and worktree creation:
   ```bash
   grep '"version"' plugins/monitor/.claude-plugin/plugin.json
   ```
   Pass the printed value into every subagent's prompt as `{expected_version}`.

   **Subagent prompt template:**

   ```
   You're doing a real end-to-end usage test of a Claude Code plugin called
   "monitor" inside a fresh clone of a small open-source project. Work only
   inside this project's folder — don't touch anything outside it. Never
   run a command that reads or lists paths outside it either — no
   `find`/`ls`/`grep` rooted at `/`, `~`, or any home-directory folder
   (Documents, Desktop, Downloads, etc.); those trigger OS permission
   prompts on the user's machine that have nothing to do with this test.

   0. Before anything else, check whether this repo's branch has moved
      since you were dispatched: run
      `grep '"version"' plugins/monitor/.claude-plugin/plugin.json` from
      the repo root you're in. If the printed version does not match
      `{expected_version}`, the branch advanced after dispatch — run
      `git merge <base-branch>` (substitute the actual branch name this
      drill is running on, e.g. `dev` or the feature branch) right now,
      before proceeding to step 1. If it matches, proceed directly to
      step 1. State in your final report which case happened.
   1. Clone {repo_url} into {project_dir} (relative to the repo root you're
      in), then cd into it. Verify the clone succeeded and contains real
      files — if it fails, or the repo is empty/archived/unrelated to what
      the name implies, stop and report that back instead of substituting
      a different repo yourself.
   2. From the repo root (one level up from {project_dir}), run:
      ./install-monitor.sh {project_dir}
   3. Companion skill level for this run: {companion_level}.
      - If "none": don't install any companion — but still let monitor's own
        `/monitor:init` probing step run normally and write `monitor/usage.md`
        showing all 6 as ABSENT. "None installed" means nothing to install,
        not "skip the probe" — those are different steps.
      - If "some": install superpowers only, project-scoped:
        - superpowers: merge into {project_dir}/.claude/settings.json —
          "extraKnownMarketplaces": {"claude-plugins-official": {"source":
          {"source": "github", "repo": "anthropics/claude-plugins-official"}}},
          "enabledPlugins": {"superpowers@claude-plugins-official": true}
        - graphify has no project-scoped install path (it only installs
          globally, outside this repo) — leave it uninstalled and let the
          probe record it ABSENT, same as any other companion you're not
          installing at this level.
      - If "all": install the 5 companions that have a project-scoped
        path (skip graphify — see above, it can't be installed without
        touching global machine state):
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
   4. Now act like a real developer who just opened this project, with no
      special knowledge of monitor beyond what you discover in the project
      itself. Look around, pick several small real things worth doing (a
      bug fix, a missing test, a docs fix, dead code removal — your call),
      and do them. Once setup above is done, the project's own
      CLAUDE.md/AGENTS.md explains how to use whatever's now available —
      follow that, in your own words, the way a real user encountering it
      cold would. Don't quote or rely on any tool/command name from these
      setup instructions; let the project's own docs teach you the
      vocabulary.
   5. Do at least 5 separate rounds of small changes so there's real log
      and report volume to inspect afterward.
   6. As part of (not separate from) those 5 rounds, use the project's
      task-tracking commands to create, update, and close at least one task
      — verify it shows up in `monitor/tasks/tasks.mtr` and appears in the
      Dashboard Tasks count.
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
      final log-entry count and report count, task count in `monitor/tasks/tasks.mtr`,
      one full task's self-reported metrics pasted verbatim, one full `--details`
      block copied verbatim from `operations.mtr` (not paraphrased) so it can be
      checked for real content vs. placeholder text, and the pending-hook test
      outcome from step 7 — pass or fail, with the warning message text pasted
      verbatim.
   ```

3. **Wait for all 3 to complete** (event-driven completion notifications —
   never poll or sleep-loop for this).

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

5. **Synthesize one combined HTML report.** Invoke the `ui-ux-pro-max`
   skill, then write a single self-contained HTML file to
   `temp/test-e2e-runs/<YYYY-MM-DD>.html` (today's date, in the **main**
   working tree — not inside any worktree). If a file for today already
   exists (a second run same day), append `-round-N` rather than
   overwriting it. Cover, per project: repo name/language, companion level, number of
   commits/changes made, log entry count, report count, task count, and
   hook-test result (pass/fail, with the one-line reason on fail) — plus a
   short findings list (bugs, inconsistencies, compliance gaps) drawn from
   both the subagent's report and your own spot-check in step 4.

6. **Publish the report** with the `Artifact` tool (`file_path` pointing at
   the HTML file just written, a short `title`/`description`, and a
   `favicon`). `SendUserFile` does not exist in this harness — don't use it.

## Notes

- This skill tests the `monitor` plugin; it is not part of it and is never
  copied into `plugins/monitor/`.
- Repos are found fresh every run — don't reuse or hardcode candidates from
  a previous run.
- **The orchestrator (you) is bound by the same containment rule as the
  subagents.** Don't run `find`/`ls`/`grep` rooted outside this repo (`/`,
  `~`, or any home-directory folder) while investigating drill state —
  scope every lookup to this repo's own path.
- **After publishing the report, run `git worktree list`.** Each
  subagent's worktree is disposable, and the harness usually auto-prunes
  it once the subagent stops — but not always: stray worktrees from a past
  run have been found still sitting there, unrelated to the current run,
  confusing enough on their own (no tracked-file changes, just an old
  untracked clone) that they were once mistaken for two agents having
  collided by accident. If any remain, `git worktree remove --force` them
  and delete the matching `worktree-agent-*` branch — don't leave this for
  "whoever runs it next."
