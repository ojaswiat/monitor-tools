#!/usr/bin/env python3
"""Generate project-specific report assets from monitor/profile.json.

Writes (all under monitor/):
  reports/template.html    the canonical report template (brand + KPIs)
  reports/index.html       the Reports listing (scanned from reports/*.html)
  index.html               the top Dashboard (links Reports, Logs, Tasks)

Reports themselves are authored by the agent from template.html; this script
only (re)builds the generated indexes. There is no manifest file — the
Reports index and Dashboard are built by scanning the reports/ directory and
reading each report's own title/branch/summary straight out of its HTML.
Nothing to hand-edit, nothing that can desync from the actual files on disk.

Usage:  python3 render_report.py --project-root <repo>
        python3 render_report.py --project-root <repo> --lock-report reports/<file>.html
        (the second form force-corrects one freshly authored report's <style>
        block back to the canonical palette and strips any <script> tag — run
        it once, right after authoring, before rebuilding the indexes below)
"""

from __future__ import annotations

import argparse
import html as _html
import re
import sys
from datetime import datetime
from pathlib import Path

import monitor_lib as mlib
import render_logs
import render_tasks

STYLE_RE = re.compile(r"<style>.*?</style>", re.S)
SCRIPT_RE = re.compile(r"<script\b.*?</script>", re.S | re.I)


def lock_report_style(root: Path, report_rel_path: str) -> bool:
    """Force a freshly authored report back onto the canonical palette/theme,
    and stamp {{ last_modified }} with the lock moment — the point a report
    is considered finalized.

    Content-tone requests (audience, reading level, language, humor) must only
    ever change the prose inside a report's sections — never its `<style>`
    block, since that block IS the design/theme lock (`mlib.PALETTE_CSS` is
    the single source of truth, shared by every generated page). This is a
    one-time correction run right after a report is authored, not a general
    "resync all reports" — running it on old reports would violate the
    immutable-snapshot rule if the canonical palette changes later.
    Also strips any `<script>` tag an authoring pass may have added (reports
    are self-contained HTML/CSS only, no `<script>`, per SKILL.md).
    Returns True if the file needed correcting.
    """
    path = mlib.monitor_dir(root) / "reports" / report_rel_path
    text = path.read_text(encoding="utf-8")
    fixed = STYLE_RE.sub(lambda _m: f"<style>{mlib.PALETTE_CSS}</style>", text, count=1)
    fixed = SCRIPT_RE.sub("", fixed)
    fixed = fixed.replace("{{ last_modified }}", datetime.now().strftime("%Y-%m-%d %H:%M"))
    if fixed != text:
        path.write_text(fixed, encoding="utf-8")
        return True
    return False


_H1_RE = re.compile(r"<h1>(.*?)</h1>", re.S)
_BRANCH_CHIP_RE = re.compile(r"<b>Branch</b><span class=\"mono\">(.*?)</span>", re.S)
_SUMMARY_RE = re.compile(
    r'<h2>Summary</h2>\s*<p>(.*?)</p>', re.S)
_TAG_RE = re.compile(r"<[^>]+>")
_RESERVED = {"index.html", "template.html"}
_PAGE_FILE_RE_TOP = re.compile(r"^page-\d+\.html$")


def _truncate(s: str, limit: int) -> str:
    """Truncate on a word boundary with an ellipsis, never mid-word."""
    if len(s) <= limit:
        return s
    cut = s[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(",.;:") + "…"


def _plain(s: str) -> str:
    """Strip tags, unescape entities to a fixpoint, collapse whitespace."""
    s = _TAG_RE.sub("", s)
    prev = None
    while prev != s:
        prev, s = s, _html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def scan_reports(root: Path) -> list[dict]:
    """Build the report list by reading reports/*.html directly — no manifest
    file. Each report's own title (<h1>), branch (its Branch meta-chip), and
    a short description (first line of its Summary section) come straight out
    of the file; date comes from the filename prefix (YYYY-MM-DD-slug.html),
    falling back to the file's mtime for anything non-conforming. Ordered
    newest-first by (date, mtime) so same-day reports still sort correctly
    without any hand-maintained index."""
    reports_dir = mlib.monitor_dir(root) / "reports"
    items: list[dict] = []
    for f in reports_dir.glob("*.html"):
        if f.name in _RESERVED or _PAGE_FILE_RE_TOP.match(f.name):
            continue
        text = f.read_text(encoding="utf-8")
        m = re.match(r"(\d{4}-\d\d-\d\d)", f.name)
        mtime = f.stat().st_mtime
        date = m.group(1) if m else datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
        h1 = _H1_RE.search(text)
        title = _plain(h1.group(1)) if h1 else f.stem
        branch_m = _BRANCH_CHIP_RE.search(text)
        branch = _plain(branch_m.group(1)) if branch_m else ""
        if branch in ("{{ branch }}", ""):
            branch = ""
        summary_m = _SUMMARY_RE.search(text)
        description = _truncate(_plain(summary_m.group(1)), 160) if summary_m else ""
        items.append({"date": date, "file": f.name, "title": title,
                      "description": description, "branch": branch,
                      "_mtime": mtime})
    items.sort(key=lambda i: (i["date"], i["_mtime"]), reverse=True)
    for it in items:
        del it["_mtime"]
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
      <span class="chip"><b>Created</b><span class="mono">{{{{ date_created }}}}</span></span>
      <span class="chip"><b>Last modified</b><span class="mono">{{{{ last_modified }}}}</span></span>
      <span class="chip"><b>Branch</b><span class="mono">{{{{ branch }}}}</span></span>
      <span class="chip"><b>Commit</b><span class="mono">{{{{ commit }}}}</span></span>
      <span class="chip"><b>Status</b><span class="tag {{{{ status_class }}}}">{{{{ status }}}}</span></span>
    </div>
  </header>

  <div class="kpis">
{kpis}  </div>"""
    body = f"""  <section class="rsection">
    <h2>Summary</h2>
    <p><!-- One coherent paragraph. Project notes: {mlib.esc(note_line)} --></p>
  </section>

  <section class="rsection">
    <h2>What Was Asked</h2>
    <p><!-- One coherent paragraph. --></p>
  </section>

  <section class="rsection">
    <h2>What Was Done</h2>
    <ul>
      <!-- One <li> per point. -->
    </ul>
  </section>

  <section class="rsection">
    <h2>Decisions &amp; Rationale</h2>
    <ul>
      <!-- One <li> per real decision: what was chosen, why, alternatives
           rejected. Pull straight from this branch's DECISION:/WHY:/
           ARCHITECTURE: log fields — don't re-derive from scratch. -->
    </ul>
  </section>

  <section class="rsection">
    <h2>Evidence</h2>
    <pre><!-- Command + output, verbatim. --></pre>
  </section>

  <section class="rsection">
    <h2>Files Touched</h2>
    <div class="table-scroll"><table><thead><tr><th>File</th><th>Change</th></tr></thead><tbody>
      <!-- One row per file. -->
    </tbody></table></div>
  </section>

  <section class="rsection">
    <h2>Risks</h2>
    <ul>
      <!-- One <li> per risk. -->
    </ul>
  </section>

  <section class="rsection">
    <h2>Gaps &amp; Assumptions</h2>
    <ul>
      <!-- One <li> per gap/assumption. Pull from this branch's GAPS:/
           ASSUMPTIONS: log fields. -->
    </ul>
  </section>

  <section class="rsection">
    <h2>Follow-ups</h2>
    <ul>
      <!-- One <li> per follow-up. -->
    </ul>
  </section>

  <section class="rsection">
    <h2>Next Steps</h2>
    <ol class="steps">
      <!-- One <li> per actionable next step. -->
    </ol>
  </section>"""
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


_REPORT_PAGE_FILE_RE = re.compile(r"^page-(\d+)\.html$")


def _prune_stale_report_pages(reports_dir: Path, total_pages: int) -> None:
    for f in reports_dir.glob("page-*.html"):
        m = _REPORT_PAGE_FILE_RE.match(f.name)
        if m and int(m.group(1)) > total_pages:
            f.unlink()


def render_reports_index(profile: dict, items: list[dict], root: Path,
                         branch: str = "") -> None:
    """Paginated Reports index — page 1 is reports/index.html, page N>1 is
    reports/page-N.html. `items` is the full newest-first report list (from scan_reports); each page
    only renders its own slice (mlib.PAGE_SIZE items)."""
    brand = mlib.project_name(profile, root)
    reports_dir = mlib.monitor_dir(root) / "reports"
    total = len(items)
    total_pages = max(1, -(-total // mlib.PAGE_SIZE))  # ceil div

    for page_num in range(1, total_pages + 1):
        start = (page_num - 1) * mlib.PAGE_SIZE
        page_items = items[start:start + mlib.PAGE_SIZE]
        header = f"""  <header class="report">
    <h1>Reports</h1>
    <p class="subtitle">Every agent-workflow run, newest first.</p>
    {mlib.tabnav("reports", "../")}
  </header>

  <div class="kpis">
    <div class="kpi"><div class="label">Current branch</div><div class="value small mono">{mlib.esc(branch or mlib.NO_BRANCH)}</div></div>
    <div class="kpi"><div class="label">Reports</div><div class="value">{total}</div></div>
    <div class="kpi"><div class="label">Latest</div><div class="value small mono">{mlib.esc(items[0]["date"] if items else "—")}</div></div>
  </div>"""
        rows, cur = [], None
        for it in page_items:
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
                 '\n      </tbody></table></div>') if page_items else \
                '  <div class="empty">No reports yet.</div>'
        table += "\n" + mlib.pagination_nav(page_num, total_pages, total)
        noun = "report" if total == 1 else "reports"
        footer = ('  <footer><span>' + str(total) + f' {noun}.</span>'
                  '<span><a href="../index.html">← Dashboard</a> · '
                  '<a href="#top">↑ Back to Top</a></span></footer>')
        title = "Reports" if total_pages <= 1 else f"Reports (page {page_num}/{total_pages})"
        out = mlib.page(f"{title} — {brand} Monitor", brand, "info",
                        "Monitor · Reports", header, table, footer, branch=branch)
        (reports_dir / mlib.page_filename(page_num)).write_text(out, encoding="utf-8")

    _prune_stale_report_pages(reports_dir, total_pages)


SEARCH_INDEX_LIMIT = mlib.PAGE_SIZE * 5


def _build_search_index(root: Path, report_items: list[dict],
                        limit: int = SEARCH_INDEX_LIMIT) -> list[dict]:
    """Small, title/summary-only index for the Dashboard's client-side grep
    box — deliberately excludes full --details/body text to keep the
    embedded payload small; this is a quick-find aid, not a replacement
    for /monitor:search's full-text matching. Capped at `limit` newest
    entries per source (logs/reports/tasks) so the embedded payload stays
    bounded the same way every other monitor page is bounded by
    mlib.PAGE_SIZE pagination; each source stops building at the cap rather
    than materializing everything first. `report_items` is the already
    scanned newest-first report list from the caller, so a Dashboard
    refresh scans reports/ exactly once.

    Log and task hits link to the paginated page that actually holds them —
    an entry at index i of the newest-first list lives on page
    i // mlib.PAGE_SIZE + 1. Report hits link to the report's own file."""
    mdir = mlib.monitor_dir(root)
    logs: list[dict] = []
    log_path = mdir / "logs" / "operations.mtr"
    if log_path.exists():
        # parse_log() is newest-first; entry position (fragments included,
        # since render_logs paginates the full list) gives the page number.
        for i, e in enumerate(render_logs.parse_log(log_path.read_text(encoding="utf-8"))):
            if e.get("fragment") is not None:
                continue
            logs.append({"kind": "log", "title": e["summary"],
                         "href": "logs/" + mlib.page_filename(i // mlib.PAGE_SIZE + 1)})
            if len(logs) >= limit:
                break
    # scan_reports() is newest-first by (date, mtime).
    reports = [{"kind": "report", "title": item["title"],
                "href": f"reports/{item['file']}"}
               for item in report_items[:limit]]
    tasks_index: list[dict] = []
    tasks_path = mdir / "tasks" / "tasks.mtr"
    if tasks_path.exists():
        # group_tasks() preserves the newest-first order of parse_tasks().
        groups = render_tasks.group_tasks(render_tasks.parse_tasks(
            tasks_path.read_text(encoding="utf-8")))
        tasks_index = [{"kind": "task", "title": g["title"] or g["task_id"],
                        "href": "tasks/" + mlib.page_filename(i // mlib.PAGE_SIZE + 1)}
                       for i, g in enumerate(groups[:limit])]
    return logs + reports + tasks_index


def _json_for_script(value) -> str:
    """JSON, escaped so it can never break out of the <script> element it is
    embedded in. JSON escaping alone does not touch `<`, `>` or `&`, so a
    title containing `</script>` would otherwise terminate the element and
    inject raw HTML into the page."""
    import json as _json
    return (_json.dumps(value)
            .replace("<", "\\u003c")
            .replace(">", "\\u003e")
            .replace("&", "\\u0026"))


def render_dashboard(profile: dict, n_reports: int, root: Path,
                     branch: str = "", report_items: list[dict] | None = None) -> None:
    """`report_items` is the newest-first list from scan_reports(); callers
    that already have it pass it in so reports/ is scanned once per refresh.
    Omitted, it is scanned here."""
    brand = mlib.project_name(profile, root)
    mdir = mlib.monitor_dir(root)
    log_path = mdir / "logs" / "operations.mtr"
    n_logs = len([e for e in render_logs.parse_log(log_path.read_text(encoding="utf-8"))
                  if e.get("fragment") is None]) if log_path.exists() else 0
    n_open_tasks = render_tasks.count_open(root)
    if report_items is None:
        report_items = scan_reports(root)
    search_index = _build_search_index(root, report_items)
    header = f"""  <header class="report">
    <h1>{mlib.esc(brand)} · Monitor</h1>
    <p class="subtitle">Reports, logs, and tasks for this project's agent workflow.</p>
    {mlib.tabnav("", "")}
  </header>

  <div class="kpis">
    <div class="kpi"><div class="label">Current branch</div><div class="value small mono">{mlib.esc(branch or mlib.NO_BRANCH)}</div></div>
    <div class="kpi"><div class="label">Reports</div><div class="value">{n_reports}</div></div>
    <div class="kpi"><div class="label">Log entries</div><div class="value">{n_logs}</div></div>
    <div class="kpi warn"><div class="label">Open tasks</div><div class="value">{n_open_tasks}</div></div>
    <div class="kpi"><div class="label">Profile</div><div class="value small mono">v{profile.get("profileVersion", 1)}</div></div>
  </div>

  <div class="dsearch">
    <input type="text" id="monitor-search" placeholder="Search titles across logs, reports, tasks..." autocomplete="off">
    <ul id="monitor-search-results"></ul>
  </div>"""
    body = """  <div class="card-grid">
    <a class="navcard" href="reports/index.html"><h3>Reports →</h3><p>Task and change reports, newest first.</p></a>
    <a class="navcard" href="logs/index.html"><h3>Logs →</h3><p>Every logged operation with status and details.</p></a>
    <a class="navcard" href="tasks/index.html"><h3>Tasks →</h3><p>Lifecycle-tracked units of work with self-reported metrics.</p></a>
  </div>"""
    footer = ('  <footer><span>monitor · project dashboard</span>'
              '<span><a href="#top">↑ Back to Top</a></span></footer>')
    script = f"""<script>
const MONITOR_SEARCH_INDEX = {_json_for_script(search_index)};
(function() {{
  const input = document.getElementById('monitor-search');
  const results = document.getElementById('monitor-search-results');
  input.addEventListener('input', function() {{
    const q = input.value.trim().toLowerCase();
    results.innerHTML = '';
    if (!q) return;
    MONITOR_SEARCH_INDEX
      .filter(item => item.title.toLowerCase().includes(q))
      .slice(0, 20)
      .forEach(item => {{
        const li = document.createElement('li');
        const a = document.createElement('a');
        a.href = item.href;
        a.textContent = '[' + item.kind + '] ' + item.title;
        li.appendChild(a);
        results.appendChild(li);
      }});
  }});
}})();
</script>"""
    out = mlib.page(f"{brand} · Monitor", brand, "info", "Monitor", header, body,
                    footer, branch=branch)
    out = out.replace('</body>', script + '\n</body>')
    (mdir / "index.html").write_text(out, encoding="utf-8")


def refresh_dashboard(root: Path) -> None:
    """Lightweight Dashboard-only refresh — recomputes both KPIs (log count
    reads operations.mtr fresh inside render_dashboard(); report count comes
    from scan_reports()) and rewrites just index.html. Called by logger.py
    after every log entry so the Dashboard's "Log entries" KPI doesn't lag
    until the next report — render_all() below is the heavier report-time
    path that also rebuilds template.html and the Reports index, neither of
    which changes on a log-only entry."""
    profile = mlib.load_profile(root)
    branch = mlib.git_branch(root)
    items = scan_reports(root)
    render_dashboard(profile, len(items), root, branch, report_items=items)


def render_all(root: Path) -> None:
    profile = mlib.load_profile(root)
    mdir = mlib.monitor_dir(root)
    (mdir / "reports").mkdir(parents=True, exist_ok=True)
    (mdir / "logs").mkdir(parents=True, exist_ok=True)
    (mdir / "tasks").mkdir(parents=True, exist_ok=True)
    branch = mlib.git_branch(root)
    render_template(profile, root)
    items = scan_reports(root)
    render_reports_index(profile, items, root, branch)
    render_dashboard(profile, len(items), root, branch, report_items=items)
    render_tasks.render(root)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mlib.add_root_arg(ap)
    ap.add_argument("--lock-report", default=None, metavar="reports/<file>.html",
                    help="Force-correct one freshly authored report's <style> "
                         "block to the canonical palette; strip any <script>. "
                         "Run once per new report, before the normal rebuild.")
    args = ap.parse_args()
    root = mlib.resolve_root(args)
    mlib.require_init(root)
    if args.lock_report:
        rel = args.lock_report.split("reports/", 1)[-1]
        changed = lock_report_style(root, rel)
        print(f"{'corrected' if changed else 'already canonical'}: {args.lock_report}")
        try:
            import pending
            pending.clear_report(root)
        except Exception as err:  # noqa: BLE001 — best-effort pending-state update
            print(f"warning: could not update pending state: {err}", file=sys.stderr)
        return 0
    render_all(root)
    print("regenerated template.html, reports/index.html, index.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
