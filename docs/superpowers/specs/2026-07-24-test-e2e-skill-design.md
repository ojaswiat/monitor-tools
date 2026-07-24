# test-e2e skill — design

## Problem

Every real dogfood pass on the `monitor` plugin so far (multiple sessions) has
been done by hand: search GitHub for a small project, clone it, install
monitor, spawn one subagent with a minimal prompt, verify its output against
raw files, report findings. It works, but it's manual, one project at a time,
and doesn't exercise monitor's new optional companion-install feature across
its full range (0 companions / some / all installed).

## Goal

A project skill, `/test-e2e`, that runs this drill 3-wide in parallel — one
project per language, one companion-install level per project — and produces
both the normal per-project monitor artifacts and one synthesized HTML
comparison report.

## Scope

Lives at `.claude/skills/test-e2e/SKILL.md` in this repo (project skill, same
convention as the existing `.claude/skills/create-readme/SKILL.md`), invoked
as `/test-e2e`. It tests the `monitor` plugin; it is not part of the plugin
itself and ships nowhere.

## Flow

```
/test-e2e
  1. rm -rf examples/*, recreate examples/ empty (each run is a fresh drill,
     not an accumulating history — the persistent artifact users actually
     want is the combined HTML report, not old clones)
  2. WebSearch fresh (no hardcoded repo list): find 1 small real
     Python CLI repo, 1 small real Node/JS CLI repo, 1 small real
     Go-or-docs-only repo
  3. Spawn 3 Agent calls (subagent_type: general-purpose) in ONE message
     so they run in parallel, run_in_background: true, no isolation flag
     (plain agents — see "Why no worktree isolation" below):
       Agent A → clone into examples/<python-slug>/   companions: NONE
       Agent B → clone into examples/<node-slug>/      companions: SOME (2-3)
       Agent C → clone into examples/<go-or-docs-slug>/ companions: ALL (6)
  4. Wait for all 3 completion notifications (event-driven, no polling)
  5. Read back each project's own monitor/ folder (profile.json,
     logs/operations.mtr, reports/*.html) plus each subagent's returned
     summary
  6. Invoke ui-ux-pro-max, then write one combined HTML report to
     temp/test-e2e-runs/<YYYY-MM-DD>.html (gitignored, same as examples/)
  7. SendUserFile the combined report
```

### Why no worktree isolation

`Agent` tool's `isolation: "worktree"` gives each subagent an isolated git
checkout of *this* repo. But the requirement is that all 3 cloned test
projects end up as sibling directories under one `examples/` folder in the
*main* working tree, inspectable together afterward — worktrees don't share
untracked directories with each other or with the main checkout, so that
would scatter the 3 examples across invisible copies instead. Since
`examples/*` are external clones with no relationship to monitor-tools' own
git history (gitignored, same treatment as the old singular `example/`),
there's nothing about them that needs git-level isolation — directory
separation (each subagent confined to its own `examples/<slug>/` by prompt)
is sufficient and is what the past manual drills already relied on.

## Subagent prompt template

One shared template, 3 slots filled per agent: `{repo_url}`, `{project_dir}`
(`examples/<slug>`), `{companion_level}` (none / some / all). Instructs the
subagent, in order:

1. `git clone {repo_url} {project_dir}`, cd into it
2. `../../install-monitor.sh {project_dir}` (relative to repo root)
3. If `{companion_level}` is some/all — install the specified companions
   using the real sources already confirmed and used this session:
   - plugins (`ui-ux-pro-max`, `superpowers`, `openwiki`): merge
     `extraKnownMarketplaces` + `enabledPlugins` into the project's
     `.claude/settings.json`
   - `npx skills add vercel-labs/skills@find-skills` /
     `npx skills add coreyhaines31/marketingskills@copywriting` (no `-g`)
   - `graphify`: `pip install graphifyy && graphify install` (global,
     shared across all 3 — only needs doing once, but safe to repeat)
4. Act as a real, only lightly-briefed developer: look around, pick several
   small real changes, make them — no monitor command names spoon-fed,
   discover monitor the way a real user would (via `CLAUDE.md`/`AGENTS.md`
   once `/monitor:init` has run)
5. Do 5+ rounds of small changes so there's real log/report volume
6. Report back: what changed, whether/how monitor got used, anything that
   looked broken, confusing, or undocumented

This mirrors the last two manual drills, parameterized into a reusable
template instead of a one-off prompt written fresh each time.

## Combined HTML report

Synthesizes, per project: language, companion level, commits made, monitor
log-entry count, report count, and a short list of findings (bugs,
inconsistencies, compliance gaps) pulled from the subagent's own summary plus
a spot-check of the raw `monitor/logs/operations.mtr` / `monitor/reports/`
files (same verification-before-trusting-subagent-claims practice used in
every manual drill so far). Styled via the `ui-ux-pro-max` skill, reusing
monitor's own design language where reasonable (not mandatory — this is a
one-off internal report, not a shipped artifact).

## Verification (this skill's own test)

This is an orchestration/technique skill, not a discipline-enforcing rule —
the RED/GREEN rationalization-testing methodology from `writing-skills`
doesn't map cleanly (there's no rule an agent might skip under pressure).
The real test is a live dry run: after writing `SKILL.md`, invoke `/test-e2e`
for real once. Pass bar: 3 subagents actually spawn against 3 different
freshly-found repos, each `examples/<slug>/monitor/` ends up with genuine
profile/logs/reports (not empty scaffolding), and the combined HTML renders
with real per-project data pulled from those files — not fabricated.

## Out of scope

- Hardcoding the 3 candidate repos (explicitly rejected — fresh WebSearch
  every run, matching the manual drills so far, accepting non-determinism)
- Persisting cross-run history/trends (each run wipes `examples/` first)
- Making this skill part of the shipped `monitor` plugin — it stays a
  project-local skill in `monitor-tools`, since it depends on this repo's own
  `install-monitor.sh` and companion-source knowledge
