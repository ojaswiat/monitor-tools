"""Integration: log two operations, author and lock a report over them, then
check what the Dashboard and Reports index actually say — the pages a real
agent (or teammate) reads to recover context."""

import logger
import render_report


PROFILE = {"project": {"name": "demo"}, "kpis": [], "notes": {},
           "profileVersion": 1}


def _author_report(root, name, title, branch, summary):
    """Author a report the way the /monitor:report flow does: fill the
    template's placeholders, then lock it."""
    (root / "monitor" / "reports").mkdir(parents=True, exist_ok=True)
    render_report.render_template(PROFILE, root)
    template = (root / "monitor" / "reports" / "template.html").read_text()
    filled = (template
              .replace("{{ title }}", title)
              .replace("{{ subtitle }}", "")
              .replace("{{ branch }}", branch)
              .replace("{{ commit }}", "abc1234..def5678")
              .replace("{{ date }}", "2026-07-27")
              .replace("{{ date_created }}", "2026-07-26")
              .replace("{{ status }}", "verified")
              .replace("{{ status_class }}", "pass")
              .replace("<h2>Summary</h2>\n    <p><!-- One coherent paragraph. "
                       "Project notes: — --></p>",
                       f"<h2>Summary</h2>\n    <p>{summary}</p>"))
    (root / "monitor" / "reports" / name).write_text(filled, encoding="utf-8")
    render_report.lock_report_style(root, name)


def test_logs_then_report_are_both_reflected_in_the_pages(project_root):
    logger.log_operation(project_root, operation="edit-file", tool="Edit",
                         summary="Rewrote the parser", status="success",
                         files=["parser.py"])
    logger.log_operation(project_root, operation="run-tests", tool="Bash",
                         summary="Ran the suite", status="failure")

    _author_report(project_root, "2026-07-27-parser.html",
                   "Parser rewrite", "feat/parser",
                   "Rewrote the parser; the suite still has one red test.")
    render_report.render_all(project_root)

    report = (project_root / "monitor" / "reports" / "2026-07-27-parser.html").read_text()
    assert "{{ last_modified }}" not in report  # stamped by --lock-report
    assert "<script" not in report.lower()

    index = (project_root / "monitor" / "reports" / "index.html").read_text()
    assert "Parser rewrite" in index
    assert "feat/parser" in index
    assert "Rewrote the parser; the suite still has one red test." in index

    dashboard = (project_root / "monitor" / "index.html").read_text()
    assert '<div class="label">Reports</div><div class="value">1</div>' in dashboard
    assert '<div class="label">Log entries</div><div class="value">2</div>' in dashboard

    logs = (project_root / "monitor" / "logs" / "index.html").read_text()
    assert "Rewrote the parser" in logs
    assert "Ran the suite" in logs
    assert '<div class="label">Failure</div><div class="value">1</div>' in logs


def test_dashboard_search_index_covers_the_logs_and_the_report(project_root):
    import json
    import re

    logger.log_operation(project_root, operation="edit-file", tool="Edit",
                         summary="Rewrote the parser", status="success")
    _author_report(project_root, "2026-07-27-parser.html", "Parser rewrite",
                   "feat/parser", "A summary.")
    render_report.render_all(project_root)

    html = (project_root / "monitor" / "index.html").read_text()
    m = re.search(r'const MONITOR_SEARCH_INDEX = (\[.*?\]);', html, re.S)
    assert m
    index = json.loads(m.group(1))
    log_hit = next(i for i in index if i["kind"] == "log")
    report_hit = next(i for i in index if i["kind"] == "report")
    assert log_hit == {"kind": "log", "title": "Rewrote the parser",
                       "href": "logs/index.html"}
    assert report_hit == {"kind": "report", "title": "Parser rewrite",
                          "href": "reports/2026-07-27-parser.html"}
