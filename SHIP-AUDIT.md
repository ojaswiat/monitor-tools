# Ship audit — stale/internal references

Read-only pass. No code changed. Found by grepping for pivot-language
("previously", "not used for", "no longer", "reverted", "upgrade", "stale",
etc.) across every shipped file, then checking each hit by hand.

## Stale references to old versions/decisions found

| # | Where | What it says | Why it's stale |
|---|---|---|---|
| 1 | `audit-report.html` (repo root, **committed to git**) | Full internal audit: deleted `feat/upgrade-to-app` branch, SQLite `log.db` (now reverted), finding IDs F-01..F-08 | Entire file is session history. Ships to anyone who clones the repo. |
| 2 | `plugins/monitor/skills/monitor/assets/base_template.html` (header comment) | "Used when profile.json has **not tailored** `template.html` yet, or when **ui-ux-pro-max is unavailable**" | Describes the old "ui-ux-pro-max designs your template" model. Current design: the template is fixed for everyone, ui-ux-pro-max is never used for design. This shipped file still says the opposite. |
| 3 | `SKILL.md`, `CLAUDE.md`, `README.md` (companion-skills line) | "ui-ux-pro-max — **not used for design** — ... so there's nothing for it to design" | Phrased as a correction to something the reader never saw happen. A fresh customer has no idea it was ever "used for design" — reads as defensive/confusing instead of just stating what it does. |
| 4 | `SKILL.md`, `CLAUDE.md`, `profile.py` docstring | "the log schema is **not** profile-driven" / "schema is locked in code, **not** profile-driven" (repeated ~4x) | Same pattern as #3 — defines the current design in terms of a past design (profile-driven schema, SQLite) the customer never had. |
| 5 | `.superpowers/sdd/` (976K, 34 files: task briefs, task reports, review diffs with commit hashes) | Raw dev-process artifacts from earlier agent sessions | Not git-tracked today, but not gitignored either — one `git add -A` away from shipping. Pure internal working notes. |
| 6 | `todo.md` (repo root, tracked, modified) | User's own running task list for this session | Not a "pivot reference" exactly, but personal scratch notes sitting in a shippable repo root. |

Not flagged (kept, on purpose): `README.md`'s "old report HTML is never rewritten," "Immutable reports," "additive/never removes" language — these describe **permanent, current** guarantees of the design, not a past version. A customer needs to know these rules going forward; they're not history.

## 1. What NOT to include when shipping

- `audit-report.html` — delete or move out of the repo entirely, don't ship it.
- `.superpowers/sdd/` — add to `.gitignore`, never ship.
- `todo.md` — either gitignore it or move your working notes somewhere outside the marketplace repo.
- Any "not X anymore" / "no longer Y" / "used to be Z" phrasing in `SKILL.md`/`CLAUDE.md`/`README.md`/`base_template.html` — rewrite as a plain positive statement of current behavior, drop the implicit contrast with a design the customer never saw.
- Nothing else needs trimming — the "immutable reports," "additive profile," "locked schema" statements are legitimate ongoing product behavior, not history, and are useful to keep.

## 2. Can a new customer see old decisions/pivots today?

**Yes, directly** — `audit-report.html` is committed to git and sitting in the repo root. Anyone who clones or browses the marketplace repo sees the full internal audit (deleted branch, abandoned SQLite design, finding IDs) immediately.

**Yes, indirectly** — `base_template.html` (a file the plugin actually ships and could fall back to) describes an old customization model that contradicts the current one. And several core docs (`SKILL.md`, `CLAUDE.md`, `README.md`) explain the current design by negating a design the customer never saw, which reads as unexplained internal history rather than product documentation.

**No** — none of this appears inside the *generated* per-project output (Dashboard/Logs/Reports HTML that `/monitor:init` creates) — only in the marketplace repo's own source/docs.
