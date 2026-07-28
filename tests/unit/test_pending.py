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


def test_check_text_keeps_open_tasks_out_of_the_yes_no_question(project_root):
    # Both pending logs/report AND open tasks: answering Y records the
    # log/report only, so the [Y/N] header must not fold the tasks in.
    tasks.start_task(project_root, title="Still running")
    data = pending.load_pending(project_root)
    data["pending_logs"] = [{"sha": "deadbeef", "message": "x", "committed_at": "now"}]
    data["pending_report"] = {"event": "merge", "since_sha": "", "detected_at": "now"}
    pending.save_pending(project_root, data)
    text = pending.check_text(project_root)
    header = text.splitlines()[0]
    assert header == ("[Warn!] Monitor: Pending logs and report. Do you want "
                      "Monitor to record now [Y/N]")
    assert "open task" not in header
    # The tasks are still surfaced, just outside the question.
    assert "Still running" in text
    assert "not part of the Y/N above" in text
    assert "/monitor:task-close" in text


def test_check_text_empty_when_nothing_pending(project_root):
    assert pending.check_text(project_root) == ""


def test_clear_log_drains_oldest_reachable_entry(project_root):
    data = pending.load_pending(project_root)
    data["pending_logs"] = [{"sha": "deadbeef", "message": "x", "committed_at": "now"}]
    pending.save_pending(project_root, data)
    pending.clear_log(project_root, "deadbeef")
    assert pending.load_pending(project_root)["pending_logs"] == []


def test_looks_like_plan_file_matches_plans_and_specs_at_any_depth():
    assert pending._looks_like_plan_file("docs/superpowers/plans/2026-01-01-x.md")
    assert pending._looks_like_plan_file("docs/specs/design.md")
    assert pending._looks_like_plan_file("specs/design.md")
    assert not pending._looks_like_plan_file("docs/README.md")
    assert not pending._looks_like_plan_file("plans.md")
    assert not pending._looks_like_plan_file("docs/plans/notes.txt")


def test_track_task_signal_noop_when_a_task_is_already_open(project_root):
    tasks.start_task(project_root, title="In progress")
    pending.track_task_signal(project_root, "docs/plans/x.md")
    assert pending.load_pending(project_root)["pending_task_signal"] is None


def test_check_text_nudges_to_start_a_task_when_none_is_open(project_root):
    pending.track_task_signal(project_root, "docs/plans/x.md")
    text = pending.check_text(project_root)
    assert text.splitlines()[0] == \
        "[Warn!] Monitor: no task tracked for recent plan/spec work."
    assert "docs/plans/x.md" in text
    assert "/monitor:task-start" in text
    assert "[Y/N]" not in text


def test_starting_a_task_clears_the_task_signal(project_root):
    pending.track_task_signal(project_root, "docs/plans/x.md")
    tasks.start_task(project_root, title="Now tracked")
    assert pending.load_pending(project_root)["pending_task_signal"] is None
    assert "no task tracked" not in pending.check_text(project_root)


def test_check_text_folds_task_signal_into_the_yes_no_message(project_root):
    pending.track_task_signal(project_root, "docs/plans/x.md")
    data = pending.load_pending(project_root)
    data["pending_logs"] = [{"sha": "deadbeef", "message": "x", "committed_at": "now"}]
    pending.save_pending(project_root, data)
    text = pending.check_text(project_root)
    assert text.splitlines()[0] == ("[Warn!] Monitor: Pending logs. Do you want "
                                     "Monitor to record now [Y/N]")
    assert "docs/plans/x.md" in text
    assert "/monitor:task-start" in text
