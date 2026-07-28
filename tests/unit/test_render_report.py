import render_report


PROFILE = {"project": {"name": "demo"}, "kpis": [], "notes": {},
           "profileVersion": 3}

REPORT_HTML = """<html><body>
  <header class="report">
    <h1>Shipped the <em>parser</em> rewrite</h1>
    <div class="meta-chips">
      <span class="chip"><b>Branch</b><span class="mono">feat/parser</span></span>
    </div>
  </header>
  <section class="rsection">
    <h2>Summary</h2>
    <p>Rewrote the parser and &amp; kept every test green.</p>
  </section>
</body></html>
"""


def _write_report(root, name, text=REPORT_HTML):
    reports = root / "monitor" / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / name).write_text(text, encoding="utf-8")
    return reports / name


def test_scan_reports_extracts_title_branch_description(project_root):
    _write_report(project_root, "2026-07-27-parser.html")
    items = render_report.scan_reports(project_root)
    assert len(items) == 1
    item = items[0]
    assert item["date"] == "2026-07-27"
    assert item["file"] == "2026-07-27-parser.html"
    assert item["title"] == "Shipped the parser rewrite"  # tags stripped
    assert item["branch"] == "feat/parser"
    assert item["description"] == "Rewrote the parser and & kept every test green."


def test_scan_reports_skips_reserved_and_page_files(project_root):
    _write_report(project_root, "2026-07-27-parser.html")
    _write_report(project_root, "index.html")
    _write_report(project_root, "template.html")
    _write_report(project_root, "page-2.html")
    files = [i["file"] for i in render_report.scan_reports(project_root)]
    assert files == ["2026-07-27-parser.html"]


def test_scan_reports_is_newest_first(project_root):
    _write_report(project_root, "2026-07-20-old.html")
    _write_report(project_root, "2026-07-27-new.html")
    files = [i["file"] for i in render_report.scan_reports(project_root)]
    assert files == ["2026-07-27-new.html", "2026-07-20-old.html"]


def test_scan_reports_blanks_an_unfilled_branch_placeholder(project_root):
    _write_report(project_root, "2026-07-27-x.html",
                  REPORT_HTML.replace("feat/parser", "{{ branch }}"))
    assert render_report.scan_reports(project_root)[0]["branch"] == ""


def test_render_dashboard_kpis_reflect_reports_logs_tasks(project_root):
    import logger
    import tasks
    _write_report(project_root, "2026-07-27-parser.html")
    logger.log_operation(project_root, operation="edit-file", tool="Edit",
                         summary="one", status="success")
    logger.log_operation(project_root, operation="edit-file", tool="Edit",
                         summary="two", status="success")
    tasks.start_task(project_root, title="Still open")

    items = render_report.scan_reports(project_root)
    render_report.render_dashboard(PROFILE, len(items), project_root, "main",
                                   report_items=items)
    html = (project_root / "monitor" / "index.html").read_text()
    for label, value in (("Reports", 1), ("Log entries", 2), ("Open tasks", 1)):
        assert (f'<div class="label">{label}</div><div class="value">{value}</div>'
                in html)
    assert '<div class="value small mono">v3</div>' in html
    assert '<div class="value small mono">main</div>' in html


def test_search_index_links_to_the_page_that_holds_the_entry(project_root):
    import monitor_lib as mlib
    import logger
    for i in range(mlib.PAGE_SIZE + 2):
        logger.log_operation(project_root, operation="edit-file", tool="Edit",
                             summary=f"entry {i}", status="success")
    index = render_report._build_search_index(project_root, [])
    by_title = {item["title"]: item["href"] for item in index}
    # Newest-first: the last two logged entries sit on page 1, the oldest
    # (entry 0) has been pushed onto page 2.
    assert by_title[f"entry {mlib.PAGE_SIZE + 1}"] == "logs/index.html"
    assert by_title["entry 0"] == "logs/page-2.html"


def test_search_index_uses_the_report_list_it_is_given(project_root):
    items = [{"title": "A report", "file": "2026-07-27-parser.html"}]
    index = render_report._build_search_index(project_root, items)
    assert index == [{"kind": "report", "title": "A report",
                      "href": "reports/2026-07-27-parser.html"}]


def test_search_index_caps_each_source(project_root):
    import logger
    for i in range(3):
        logger.log_operation(project_root, operation="edit-file", tool="Edit",
                             summary=f"entry {i}", status="success")
    index = render_report._build_search_index(project_root, [], limit=2)
    assert len([i for i in index if i["kind"] == "log"]) == 2
