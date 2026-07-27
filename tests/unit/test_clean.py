import re
import time

import clean
import tasks


def test_clean_tasks_removes_by_creation_order(project_root):
    a_id = tasks.start_task(project_root, title="Task A (really oldest)")
    time.sleep(1.1)
    tasks.start_task(project_root, title="Task B (really newest)")
    time.sleep(1.1)
    tasks.update_task(project_root, task_id=a_id, status="in_progress", summary="still going")
    clean.clean_tasks(project_root, 1, dry=False)
    text = (project_root / "monitor" / "tasks" / "tasks.mtr").read_text()
    assert f"task_id: {a_id}" not in text
    assert "Task B" in text


def test_clean_tasks_never_deletes_by_substring_mention(project_root):
    victim_id = tasks.start_task(project_root, title="Victim")
    survivor_id = tasks.start_task(project_root, title="Survivor")
    tasks.update_task(project_root, task_id=survivor_id, status="in_progress",
                      summary="ref", details=f"follow-on from task_id: {victim_id}")
    time.sleep(1.1)
    tasks.close_task(project_root, task_id=survivor_id, status="success", summary="done")
    clean.clean_tasks(project_root, 1, dry=False)  # should remove only the oldest (victim)
    text = (project_root / "monitor" / "tasks" / "tasks.mtr").read_text()
    # A mere textual mention of the victim's id (e.g. inside another task's
    # `details:` line) must not count as "the victim survived" -- only an
    # actual `task_id: <id>` line (the real per-event field) does. Anchor
    # the check the same way tasks.py itself identifies task_id lines.
    assert not re.search(rf"^task_id: {victim_id}$", text, re.M)
    assert re.search(rf"^task_id: {survivor_id}$", text, re.M)
