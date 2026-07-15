#!/usr/bin/env python3
"""Generate project-specific report assets from monitor/profile.json.

Writes (all under monitor/):
  logs/schema.json         from profile.logFields (versioned, additive)
  reports/template.html    the canonical report template (brand + KPIs)
  reports/index.html       the Reports listing (from reports/manifest.json)
  index.html               the top Dashboard (links Reports + Logs)

Reports themselves are authored by the agent from template.html; this script
only (re)builds the generated indexes/schema. A manifest is seeded from any
existing index the first time so historical reports are preserved.

Usage:  python3 render_report.py --project-root <repo>
"""

from __future__ import annotations

import argparse
import html as _html
import re
import sys
from pathlib import Path

import monitor_lib as mlib
import render_logs

ROW_RE = re.compile(
    r'<td class="timestamp">([^<]*)</td>\s*'
    r'<td><a href="([^"]+)">(.*?)</a></td>\s*'
    r'<td class="description">(.*?)</td>', re.S)


def build_schema(profile: dict) -> dict:
    fields = profile.get("logFields", [])
    schema = {"schemaVersion": int(profile.get("profileVersion", 1)),
              "required": [f["key"] for f in fields if f.get("required")],
              "fields": {}}
    for f in fields:
        spec = {"required": bool(f.get("required"))}
        if "enum" in f:
            spec["enum"] = f["enum"]
        if "type" in f:
            spec["type"] = f["type"]
        schema["fields"][f["key"]] = spec
    return schema


def seed_manifest(root: Path) -> list[dict]:
    """Build reports/manifest.json from an existing index if none exists.

    Manifest invariant: newest-first (new entries are prepended at index 0). We
    ENFORCE it on every load with a stable date-descending sort — this keeps the
    within-date order (already newest-first) intact while preventing an appended
    entry from corrupting cross-date order over time.
    """
    mdir = mlib.monitor_dir(root)
    man_path = mdir / "reports" / "manifest.json"
    existing = mlib.load_json(man_path, None)
    if existing is not None:
        ordered = sorted(existing, key=lambda i: i.get("date", ""), reverse=True)
        if ordered != existing:  # persist the repair only when order changed
            mlib.save_json(man_path, ordered)
        return ordered
    def plain(s: str) -> str:
        # Unescape to a fixpoint so re-seeding from an already-escaped index
        # can't accumulate &amp;amp;… — render escapes exactly once afterwards.
        prev = None
        while prev != s:
            prev, s = s, _html.unescape(s)
        return s.strip()

    def file_date(name: str, fallback: str = "") -> str:
        # The filename prefix (YYYY-MM-DD-slug.html) is the canonical date;
        # timestamp cells in older reports hold a time-of-day, not a date.
        return name[:10] if re.match(r"\d{4}-\d\d-\d\d", name) else fallback

    items: list[dict] = []
    for idx in (mdir / "reports" / "index.html", mdir / "index.html"):
        if idx.exists():
            for date, href, title, desc in ROW_RE.findall(idx.read_text(encoding="utf-8")):
                file = href.split("/")[-1]
                if file and file != "index.html" and not any(i["file"] == file for i in items):
                    items.append({"date": file_date(file, date.strip()), "file": file,
                                  "title": plain(title), "description": plain(desc)})
    # Fall back to scanning report files for any not captured above.
    for f in sorted((mdir / "reports").glob("20*-*.html"), reverse=True):
        if f.name == "index.html" or any(i["file"] == f.name for i in items):
            continue
        m = re.search(r"<h1>(.*?)</h1>", f.read_text(encoding="utf-8"), re.S)
        title = plain(re.sub(r"\s+", " ", m.group(1))) if m else f.stem
        items.append({"date": file_date(f.name), "file": f.name, "title": title,
                      "description": ""})
    # Stable sort by date desc — preserves each day's curated newest-first order.
    items.sort(key=lambda i: i["date"], reverse=True)
    mlib.save_json(man_path, items)
    return items


def render_template(profile: dict, root: Path) -> None:
    brand = mlib.project_name(profile, root)
    notes = profile.get("notes", {})
    note_line = " · ".join(f"{k}: {v}" for k, v in notes.items()) or "—"
    kpis = "".join(
        f'    <div class="kpi"><div class="label">{mlib.esc(k.get("label", k["key"]))}</div>'
        f'<div class="value">{{{{ {mlib.esc(k["key"])} }}}}</div></div>\n'
        for k in profile.get("kpis", []))
    header = f"""  <header class="report">
    <h1>{{{{ title }}}}</h1>
    <p class="subtitle">{{{{ subtitle }}}}</p>
    <div class="meta-chips">
      <span class="chip"><b>Generated</b><span class="mono">{{{{ date }}}}</span></span>
      <span class="chip"><b>Branch</b><span class="mono">{{{{ branch }}}}</span></span>
      <span class="chip"><b>Commit</b><span class="mono">{{{{ commit }}}}</span></span>
      <span class="chip"><b>Status</b><span class="tag {{{{ status_class }}}}">{{{{ status }}}}</span></span>
    </div>
  </header>

  <div class="kpis">
{kpis}  </div>"""
    body = f"""  <div class="table-scroll"><table><tbody>
    <tr><td><!-- Fill sections: Summary · What Was Asked · What Was Done ·
      Evidence (pre) · Files Touched · Risks · Follow-ups · Next Steps.
      Project notes: {mlib.esc(note_line)} --></td></tr>
  </tbody></table></div>"""
    footer = ('  <footer><span>Generated by the monitor workflow.</span>'
              '<span><a href="index.html">← All reports</a> · '
              '<a href="#top">↑ Back to Top</a></span></footer>')
    # Report pages carry a Back link to the reports index (same dir).
    masthead_extra = (f'    <a class="back" href="index.html" '
                      f'aria-label="Back to reports">{mlib.BACK_SVG}Back</a>\n')
    # The masthead chip is a placeholder here: a report is a snapshot, so it
    # records the branch the work was done on, not the branch you read it from.
    html = mlib.page(f"{{{{ title }}}} — {brand} Report", brand, "info",
                     "Monitor · Report", header, body, footer,
                     branch="{{ branch }}")
    html = html.replace('  <div class="masthead" id="top">\n',
                        '  <div class="masthead" id="top">\n' + masthead_extra)
    (mlib.monitor_dir(root) / "reports" / "template.html").write_text(html, encoding="utf-8")


def render_reports_index(profile: dict, items: list[dict], root: Path,
                         branch: str = "") -> None:
    brand = mlib.project_name(profile, root)
    header = f"""  <header class="report">
    <h1>Reports</h1>
    <p class="subtitle">Every agent-workflow run, newest first.</p>
    {mlib.tabnav("reports", "../")}
  </header>

  <div class="kpis">
    <div class="kpi"><div class="label">Current branch</div><div class="value small mono">{mlib.esc(branch or mlib.NO_BRANCH)}</div></div>
    <div class="kpi"><div class="label">Reports</div><div class="value">{len(items)}</div></div>
    <div class="kpi"><div class="label">Latest</div><div class="value small mono">{mlib.esc(items[0]["date"] if items else "—")}</div></div>
  </div>"""
    rows, cur = [], None
    for it in items:
        if it["date"] != cur:
            cur = it["date"]
            rows.append(f'        <tr class="day-divider"><td colspan="2">{mlib.esc(cur)}</td></tr>')
        # Per-report branch: the branch that report's work was done on. Omitted
        # for entries that predate the field rather than shown as "no branch".
        chip = ("<div>" + mlib.branch_chip(it["branch"]) + "</div>") \
            if it.get("branch") else ""
        rows.append(
            f'        <tr><td><a href="{mlib.esc(it["file"])}">{mlib.esc(it["title"])}</a>'
            f'<div class="description">{mlib.esc(it.get("description", ""))}</div>{chip}</td>'
            f'<td class="timestamp">{mlib.esc(it["date"])}</td></tr>')
    table = ('  <div class="table-scroll"><table><thead><tr><th>Report</th>'
             '<th>Date</th></tr></thead><tbody>\n' + "\n".join(rows) +
             '\n      </tbody></table></div>') if items else \
            '  <div class="empty">No reports yet.</div>'
    footer = ('  <footer><span>' + str(len(items)) + ' reports.</span>'
              '<span><a href="../index.html">← Dashboard</a> · '
              '<a href="#top">↑ Back to Top</a></span></footer>')
    out = mlib.page(f"Reports — {brand} Monitor", brand, "info",
                    "Monitor · Reports", header, table, footer, branch=branch)
    (mlib.monitor_dir(root) / "reports" / "index.html").write_text(out, encoding="utf-8")


def render_dashboard(profile: dict, n_reports: int, root: Path,
                     branch: str = "") -> None:
    brand = mlib.project_name(profile, root)
    mdir = mlib.monitor_dir(root)
    log_text = (mdir / "logs" / "operations.log")
    n_logs = len(render_logs.parse_log(log_text.read_text(encoding="utf-8"))) \
        if log_text.exists() else 0
    header = f"""  <header class="report">
    <h1>{mlib.esc(brand)} · Monitor</h1>
    <p class="subtitle">Reports and logs for this project's agent workflow.</p>
    {mlib.tabnav("", "")}
  </header>

  <div class="kpis">
    <div class="kpi"><div class="label">Current branch</div><div class="value small mono">{mlib.esc(branch or mlib.NO_BRANCH)}</div></div>
    <div class="kpi"><div class="label">Reports</div><div class="value">{n_reports}</div></div>
    <div class="kpi"><div class="label">Log entries</div><div class="value">{n_logs}</div></div>
    <div class="kpi"><div class="label">Profile</div><div class="value small mono">v{profile.get("profileVersion", 1)}</div></div>
  </div>"""
    body = """  <div class="card-grid">
    <a class="navcard" href="reports/index.html"><h3>Reports →</h3><p>Task and change reports, newest first.</p></a>
    <a class="navcard" href="logs/index.html"><h3>Logs →</h3><p>Every logged operation with status and details.</p></a>
  </div>"""
    footer = ('  <footer><span>monitor · project dashboard</span>'
              '<span><a href="#top">↑ Back to Top</a></span></footer>')
    out = mlib.page(f"{brand} · Monitor", brand, "info", "Monitor", header, body,
                    footer, branch=branch)
    (mdir / "index.html").write_text(out, encoding="utf-8")


def render_all(root: Path) -> None:
    profile = mlib.load_profile(root)
    mdir = mlib.monitor_dir(root)
    (mdir / "reports").mkdir(parents=True, exist_ok=True)
    (mdir / "logs").mkdir(parents=True, exist_ok=True)
    branch = mlib.git_branch(root)
    mlib.save_json(mdir / "logs" / "schema.json", build_schema(profile))
    render_template(profile, root)
    items = seed_manifest(root)
    render_reports_index(profile, items, root, branch)
    render_dashboard(profile, len(items), root, branch)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mlib.add_root_arg(ap)
    args = ap.parse_args()
    root = mlib.resolve_root(args)
    mlib.require_init(root)
    render_all(root)
    print("regenerated schema.json, template.html, reports/index.html, index.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
