#!/usr/bin/env python3
"""Detect and reconcile monitor/profile.json — the project's source of truth.

Monitor has exactly two jobs: log and report. It does not detect a project's
language, guess its build/test commands, or otherwise inspect what the
project *is* or *does* — that would be guessing, not recording. The only
thing profile.json auto-fills is the project's own directory name (needed to
brand the Dashboard/Reports/Logs pages) — nothing else is detected.

Reconcile is strictly ADDITIVE: new detected keys/fields are added (stamped with
the new profileVersion); keys already present are left as-is (hand edits win);
nothing is ever removed or renamed. This is what makes template upgrades
backward compatible.

Usage:  python3 profile.py --project-root <repo>   [--print]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import monitor_lib as mlib

# The "since" on each entry below is documentation only — _merge_list() always
# stamps the actual reconcile-time version on write, so these literals never
# reach a profile.json as-is.
DEFAULT_KPIS = [
    {"key": "tests",  "label": "Tests",  "since": 1},
    {"key": "commit", "label": "Commit", "since": 1},
]


def detect(root: Path) -> dict:
    """The only thing auto-filled: the project's own directory name, for
    branding pages. No language/build/test guessing, no code execution."""
    return {"project": {"name": root.name}}


def _merge_list(existing: list, defaults: list, added: list, kind: str,
                version: int) -> list:
    """Merge default field/kpi entries into existing by 'key', additively."""
    out = list(existing)
    have = {e.get("key") for e in existing}
    for item in defaults:
        if item.get("key") not in have:
            entry = dict(item)
            entry["since"] = version
            out.append(entry)
            added.append(f"{kind}:{item['key']}")
    return out


def reconcile(existing: dict, det: dict) -> tuple[dict, list]:
    added: list[str] = []
    version = int(existing.get("profileVersion", 0)) + 1
    prof = dict(existing)
    prof["profileVersion"] = version

    # project: fill only missing keys (hand edits win).
    proj = dict(existing.get("project", {}))
    for k, v in det.get("project", {}).items():
        if k not in proj:
            proj[k] = v
            added.append(f"project.{k}")
    prof["project"] = proj

    prof["kpis"] = _merge_list(existing.get("kpis", []), DEFAULT_KPIS,
                               added, "kpi", version)
    prof.setdefault("notes", existing.get("notes", {}))
    return prof, added


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mlib.add_root_arg(ap)
    ap.add_argument("--print", action="store_true", help="Print result only")
    args = ap.parse_args()
    root = mlib.resolve_root(args)
    existing = mlib.load_profile(root)
    prof, added = reconcile(existing, detect(root))
    if not args.print:
        mlib.save_json(mlib.monitor_dir(root) / "profile.json", prof)
    print(f"profileVersion={prof['profileVersion']} "
          f"({'created' if not existing else 'reconciled'})")
    if added:
        print("added: " + ", ".join(added))
    else:
        print("added: (nothing new)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
