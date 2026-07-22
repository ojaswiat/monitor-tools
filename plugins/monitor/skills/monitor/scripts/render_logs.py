#!/usr/bin/env python3
"""Render monitor/logs/log.db into monitor/logs/index.html (Logs page).

log.db stays canonical; this is just a read-only view of it. Called by
logger.py after every entry; also runnable standalone.

Usage:  python3 render_logs.py --project-root <repo>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import db
import monitor_lib as mlib

STATUS_TAG = {"success": "pass", "partial": "warn", "failure": "fail"}
STATUS_CARD = {"success": "success", "partial": "partial", "failure": "fail"}


def _card(e: dict) -> str:
    card_cls = STATUS_CARD.get(e["status"], "")
    tag_cls = STATUS_TAG.get(e["status"], "info")
    tag_label = e["status"].upper() if e["status"] else "LOGGED"
    p = [f'  <article class="logcard {card_cls}">', '    <div class="row">',
         f'      <time>{mlib.esc(e["timestamp"])}</time>',
         f'      <span class="op">{mlib.esc(e["operation"])}</span>']
    if e["tool"]:
        p.append(f'      <span class="toolchip">{mlib.esc(e["tool"])}</span>')
    # The branch this operation was made on. Omitted (not "no branch") when the
    # entry predates the field, so old entries stay clean rather than look wrong.
    if e.get("branch"):
        p.append("      " + mlib.branch_chip(e["branch"]))
    for k, v in e["extra"].items():
        p.append(f'      <span class="xchip">{mlib.esc(k)}: {mlib.esc(v)}</span>')
    p.append('      <span class="spacer"></span>')
    p.append(f'      <span class="tag {tag_cls}">{mlib.esc(tag_label)}</span>')
    p.append('    </div>')
    if e["summary"]:
        p.append(f'    <p class="summary">{mlib.esc(e["summary"])}</p>')
    if e["task"]:
        p.append(f'    <p class="task"><b>Task</b> {mlib.esc(e["task"])}</p>')
    if e["files"]:
        chips = "".join(f'<span class="file">{mlib.esc(f)}</span>' for f in e["files"])
        p.append(f'    <div class="files">{chips}</div>')
    if e["details"]:
        p += ['    <details>', '      <summary>Details</summary>',
              f'      {mlib.format_list_block(e["details"])}', '    </details>']
    p.append('  </article>')
    return "\n".join(p)


def build_html(entries: list[dict], brand: str, branch: str = "") -> str:
    total = len(entries)
    counts = {"success": 0, "partial": 0, "failure": 0}
    for e in entries:
        if e["status"] in counts:
            counts[e["status"]] += 1
    last = entries[0]["timestamp"] if entries else "—"
    header = f"""  <header class="report">
    <h1>Logs</h1>
    <p class="subtitle">Agent operation log — newest first. Rendered from <code>monitor/logs/log.db</code>.</p>
    {mlib.tabnav("logs", "../")}
  </header>

  <div class="kpis">
    <div class="kpi"><div class="label">Current branch</div><div class="value small mono">{mlib.esc(branch or mlib.NO_BRANCH)}</div></div>
    <div class="kpi"><div class="label">Total ops</div><div class="value">{total}</div></div>
    <div class="kpi pass"><div class="label">Success</div><div class="value">{counts['success']}</div></div>
    <div class="kpi warn"><div class="label">Partial</div><div class="value">{counts['partial']}</div></div>
    <div class="kpi fail"><div class="label">Failure</div><div class="value">{counts['failure']}</div></div>
    <div class="kpi"><div class="label">Last activity</div><div class="value small mono">{mlib.esc(last)}</div></div>
  </div>

  <fieldset class="filter" aria-label="Filter by status">
    <span class="flabel">Filter</span>
    <input type="radio" name="f" id="f-all" checked>
    <input type="radio" name="f" id="f-success">
    <input type="radio" name="f" id="f-partial">
    <input type="radio" name="f" id="f-fail">
    <label for="f-all">All</label><label for="f-success">Success</label>
    <label for="f-partial">Partial</label><label for="f-fail">Failure</label>
  </fieldset>"""
    if entries:
        body = '  <div class="log">\n' + "\n".join(_card(e) for e in entries) + "\n  </div>"
    else:
        body = '  <div class="empty">No operations logged yet.</div>'
    footer = (f'  <footer><span>Rendered from monitor/logs/log.db · {total} entries.</span>'
              f'<span><a href="../index.html">← Dashboard</a> · <a href="#top">↑ Back to Top</a></span></footer>')
    return mlib.page(f"Logs — {brand} Monitor", brand, "info", "Monitor · Logs",
                     header, body, footer, branch=branch)


def render(root: Path) -> Path:
    mdir = mlib.monitor_dir(root)
    out = mdir / "logs" / "index.html"
    profile = mlib.load_profile(root)
    brand = mlib.project_name(profile, root)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_html(db.fetch_all(root), brand, mlib.git_branch(root)),
                   encoding="utf-8")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mlib.add_root_arg(ap)
    args = ap.parse_args()
    root = mlib.resolve_root(args)
    mlib.require_init(root)
    db.init_db(root)
    print(f"wrote {render(root)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
