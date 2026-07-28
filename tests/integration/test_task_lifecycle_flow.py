"""Integration: the full start -> update -> close flow, checked against the
rendered HTML, not just the .mtr text — this is what a real agent session
actually looks at."""

import tasks
import render_tasks


def test_full_lifecycle_renders_correct_dashboard_kpi(project_root):
    task_id = tasks.start_task(project_root, title="Ship the thing")
    assert render_tasks.count_open(project_root) == 1
    tasks.update_task(project_root, task_id=task_id, status="in_progress", summary="working")
    assert render_tasks.count_open(project_root) == 1
    tasks.close_task(project_root, task_id=task_id, status="success", summary="shipped")
    assert render_tasks.count_open(project_root) == 0
    html = (project_root / "monitor" / "tasks" / "index.html").read_text()
    assert task_id in html
    assert "SUCCESS" in html
