"""Integration: the Dashboard's embedded search index actually contains
real entries from all three sources after a full log+report+task round."""

import json
import re

import tasks


def test_dashboard_embeds_searchable_index(project_root):
    import logger
    logger.log_operation(project_root, operation="fix-bug", tool="Edit",
                         summary="Fixed the login bug", status="success")
    tasks.start_task(project_root, title="Ship the login fix")

    import render_report
    profile = {"project": {"name": "demo"}, "kpis": [], "notes": {}}
    render_report.render_dashboard(profile, 0, project_root, "main")

    html = (project_root / "monitor" / "index.html").read_text()
    m = re.search(r'const MONITOR_SEARCH_INDEX = (\[.*?\]);', html, re.S)
    assert m, "expected an embedded MONITOR_SEARCH_INDEX array in index.html"
    index = json.loads(m.group(1))
    titles = [item["title"] for item in index]
    assert any("login bug" in t for t in titles)
    assert any("login fix" in t for t in titles)
    assert '<input' in html and 'id="monitor-search"' in html
