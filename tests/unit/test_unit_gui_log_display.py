def test_construction_headless(qapp, log_display):
    widget = log_display()
    assert widget.viewer is not None


def test_print_appends(qapp, log_display):
    widget = log_display()
    widget.print("line one")
    widget.print("line two")
    assert widget.viewer.toPlainText() == "line one\nline two"
