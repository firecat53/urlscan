"""The header shows the open mode and queue size; the footer shows search
state and messages.

"""

import pytest

from tui_harness import URLS, gui_browser, make_chooser, only_opened, run_with_keys  # noqa: F401


def header_text(chooser):
    header = chooser.top.base_widget.header
    return None if header is None else header.base_widget.text


def footer(chooser):
    """The footer's text and display attribute."""
    footer = chooser.top.base_widget.footer
    return footer.base_widget.text, footer.attr_map[None]


@pytest.mark.parametrize("keys", ["q", "aq", "adq", "lq"],
                         ids=["start", "add", "delete", "link_handler"])
def test_nohelp_hides_header(tmp_path, keys):
    chooser = make_chooser(tmp_path / "opened", nohelp=True)
    run_with_keys(chooser, keys)
    assert header_text(chooser) is None


def test_nohelp_hides_header_after_opening_queue(tmp_path):
    log = tmp_path / "opened"
    chooser = make_chooser(log, nohelp=True)
    run_with_keys(chooser, "aoq")
    # Wait for the queue's worker thread before the next test starts.
    assert only_opened(log, URLS[:1])
    assert header_text(chooser) is None


@pytest.mark.parametrize("keys, queue_size", [
    ("q", 0),
    ("ajaq", 2),
    ("ajadq", 1),
])
def test_header_shows_queue_size(tmp_path, keys, queue_size):
    chooser = make_chooser(tmp_path / "opened")
    run_with_keys(chooser, keys)
    assert header_text(chooser).endswith(f"Queue - {queue_size}")


def test_header_shows_open_mode(tmp_path):
    chooser = make_chooser(tmp_path / "opened")
    run_with_keys(chooser, "lq")
    assert f"URL opening mode - {chooser.link_open_modes[0]} ::" in header_text(chooser)
    assert chooser.link_open_modes[0] != chooser.runsafe


def test_no_footer_at_start(tmp_path):
    chooser = make_chooser(tmp_path / "opened")
    run_with_keys(chooser, "q")
    assert chooser.top.base_widget.footer is None


@pytest.mark.parametrize("keys, expected", [
    ("/second\rq", ("Search: second", "search")),
    ("/zzzz\rq", ("", "default")),    # no matches: search dropped
])
def test_search_footer(tmp_path, keys, expected):
    chooser = make_chooser(tmp_path / "opened")
    run_with_keys(chooser, keys)
    assert footer(chooser) == expected


def test_selection_footer(tmp_path):
    chooser = make_chooser(tmp_path / "opened")
    run_with_keys(chooser, "2q")
    assert footer(chooser) == ("Selection: 2", "footer")
