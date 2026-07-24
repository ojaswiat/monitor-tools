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
