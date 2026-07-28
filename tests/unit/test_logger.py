import pytest

import logger


def _base_entry(**over):
    entry = {"timestamp": "2026-07-27 10:00:00,000", "level": "INFO",
             "operation": "edit-file", "tool": "Edit", "summary": "did a thing",
             "status": "success"}
    entry.update(over)
    return entry


def test_validate_accepts_a_complete_entry():
    logger.validate(_base_entry())  # no raise


@pytest.mark.parametrize("field", logger.REQUIRED)
def test_validate_rejects_each_missing_required_field(field):
    entry = _base_entry(**{field: ""})
    with pytest.raises(ValueError, match="missing required fields"):
        logger.validate(entry)


def test_validate_rejects_unknown_level():
    with pytest.raises(ValueError, match="level must be one of"):
        logger.validate(_base_entry(level="TRACE"))


def test_validate_rejects_unknown_status():
    with pytest.raises(ValueError, match="status must be one of"):
        logger.validate(_base_entry(status="done"))


def test_render_entry_header_and_fields():
    block = logger.render_entry(_base_entry(branch="main", task_id="abcd1234",
                                            files=["a.py", "b.py"],
                                            details="DECISION: x"))
    lines = block.split("\n")
    assert lines[0] == ("2026-07-27 10:00:00,000 INFO [edit-file] (Edit) "
                        "did a thing -- success")
    assert "branch:  main" in lines
    assert "task_id: abcd1234" in lines
    assert "files:   a.py, b.py" in lines
    assert "details: DECISION: x" in lines


def test_log_operation_writes_a_well_formed_block(project_root):
    logger.log_operation(project_root, operation="edit-file", tool="Edit",
                         summary="Touched the parser", status="success",
                         files=["parser.py"])
    text = (project_root / "monitor" / "logs" / "operations.mtr").read_text()
    assert "[edit-file] (Edit) Touched the parser -- success" in text
    assert "files:   parser.py" in text
    assert text.rstrip("\n").endswith("=" * 80)


def test_log_operation_prepends_newest_first(project_root):
    logger.log_operation(project_root, operation="first", tool="Edit",
                         summary="oldest", status="success")
    logger.log_operation(project_root, operation="second", tool="Edit",
                         summary="newest", status="success")
    text = (project_root / "monitor" / "logs" / "operations.mtr").read_text()
    assert text.index("[second]") < text.index("[first]")


def test_log_operation_sanitizes_control_characters(project_root):
    logger.log_operation(project_root, operation="edit-file", tool="Edit",
                         summary="line one\nline two", status="success")
    text = (project_root / "monitor" / "logs" / "operations.mtr").read_text()
    # A raw newline in the summary would forge a second header line.
    assert "line one\nline two" not in text
    assert "line one" in text


def test_log_operation_rejects_bad_status_before_writing(project_root):
    with pytest.raises(ValueError, match="status must be one of"):
        logger.log_operation(project_root, operation="edit-file", tool="Edit",
                             summary="nope", status="oops")
    assert not (project_root / "monitor" / "logs" / "operations.mtr").exists()


def test_log_operation_refreshes_logs_page_and_dashboard(project_root):
    logger.log_operation(project_root, operation="edit-file", tool="Edit",
                         summary="Refreshes the views", status="success")
    logs_html = (project_root / "monitor" / "logs" / "index.html").read_text()
    assert "Refreshes the views" in logs_html
    dashboard = (project_root / "monitor" / "index.html").read_text()
    assert "Log entries" in dashboard
    assert '<div class="value">1</div>' in dashboard
