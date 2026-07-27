import search
import tasks


def test_search_tasks_matches_details(project_root):
    task_id = tasks.start_task(project_root, title="Fix the thing",
                               details="DECISION: use approach X")
    matches = search.search_tasks(project_root, "approach X")
    assert len(matches) == 1
    assert matches[0]["task_id"] == task_id


def test_search_reports_matches_body_text(project_root):
    reports_dir = project_root / "monitor" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "2026-07-27-demo.html").write_text(
        "<html><body><h1>Demo Report</h1><p>Fixed the flibbertigibbet bug.</p></body></html>")
    matches = search.search_reports(project_root, "flibbertigibbet")
    assert len(matches) == 1
    assert matches[0]["title"] == "Demo Report"


def test_search_scope_all_covers_every_source(project_root):
    tasks.start_task(project_root, title="uniqueword task")
    import logger
    logger.log_operation(project_root, operation="op", tool="Bash",
                         summary="uniqueword log", status="success")
    matches = search.search(project_root, "uniqueword", scope="all")
    assert set(matches.keys()) == {"logs", "reports", "tasks"}
    assert len(matches["logs"]) == 1
    assert len(matches["tasks"]) == 1
    assert len(matches["reports"]) == 0
