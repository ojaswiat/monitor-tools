import monitor_lib as mlib


def test_sanitize_strips_control_chars():
    assert mlib.sanitize("hello\x00\x1bworld") == "helloworld"


def test_sanitize_flattens_real_newlines():
    assert mlib.sanitize("line one\nline two\r\nline three") == "line one line two line three"


def test_sanitize_trims_whitespace():
    assert mlib.sanitize("  padded  ") == "padded"


def test_sanitize_none_passes_through():
    assert mlib.sanitize(None) is None
