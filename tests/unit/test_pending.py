import pending
import tasks


def test_open_tasks_lists_nonterminal_only(project_root):
    tasks.start_task(project_root, title="Still open")
    closed_id = tasks.start_task(project_root, title="Will close")
    tasks.close_task(project_root, task_id=closed_id, status="success", summary="done")
    open_list = pending.open_tasks(project_root)
    assert len(open_list) == 1
    assert open_list[0]["title"] == "Still open"


def test_check_text_mentions_open_task(project_root):
    tasks.start_task(project_root, title="Needs attention")
    text = pending.check_text(project_root)
    assert "Needs attention" in text
    assert "open task" in text


def test_check_text_omits_log_report_instructions_when_only_tasks_open(project_root):
    tasks.start_task(project_root, title="Only a task")
    text = pending.check_text(project_root)
    assert "Only a task" in text
    assert "run /monitor:log for it" not in text
    assert "/monitor:report" not in text
    assert "/monitor:task-close" in text


def test_check_text_task_only_header_is_not_a_question(project_root):
    tasks.start_task(project_root, title="Only a task")
    text = pending.check_text(project_root)
    assert text.splitlines()[0] == "[Warn!] Monitor: 1 open task."
    assert "[Y/N]" not in text
    assert "Do you want Monitor to record" not in text


def test_check_text_task_only_header_pluralizes(project_root):
    tasks.start_task(project_root, title="First")
    tasks.start_task(project_root, title="Second")
    assert pending.check_text(project_root).splitlines()[0] == \
        "[Warn!] Monitor: 2 open tasks."


def test_check_text_keeps_question_when_logs_pending(project_root):
    data = pending.load_pending(project_root)
    data["pending_logs"] = [{"sha": "deadbeef", "message": "x", "committed_at": "now"}]
    pending.save_pending(project_root, data)
    assert "[Y/N]" in pending.check_text(project_root)


def test_pending_phrase_joins_three_parts_with_oxford_comma(project_root):
    data = {"pending_logs": [{"sha": "a"}], "pending_report": {"event": "merge"}}
    assert pending._pending_phrase(data, 2) == "logs, report, and 2 open tasks"
    assert pending._pending_phrase(data, 0) == "logs and report"
    assert pending._pending_phrase({"pending_logs": [{"sha": "a"}]}, 0) == "logs"


def test_check_text_includes_instructions_when_logs_pending(project_root):
    data = pending.load_pending(project_root)
    data["pending_logs"] = [{"sha": "deadbeef", "message": "x", "committed_at": "now"}]
    pending.save_pending(project_root, data)
    text = pending.check_text(project_root)
    assert "run /monitor:log for it" in text


def test_check_text_empty_when_nothing_pending(project_root):
    assert pending.check_text(project_root) == ""


def test_clear_log_drains_oldest_reachable_entry(project_root):
    data = pending.load_pending(project_root)
    data["pending_logs"] = [{"sha": "deadbeef", "message": "x", "committed_at": "now"}]
    pending.save_pending(project_root, data)
    pending.clear_log(project_root, "deadbeef")
    assert pending.load_pending(project_root)["pending_logs"] == []
