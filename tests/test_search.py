"""Searching with / filters the list; Enter ends the search."""

import pytest

from tui_harness import gui_browser, make_chooser, only_opened, run_with_keys  # noqa: F401

FIRST = "https://one.example.com/a"
SECOND = "https://two.example.com/b"
MESSAGE = f"Subject: test\n\nFirst link {FIRST}\n\nSecond link {SECOND}\n"


def test_enter_ends_search_without_opening(tmp_path):
    """Space is part of the search string, and Enter ends the search without
    opening anything. After that, keys work normally again.

    """
    log = tmp_path / "opened"
    chooser = make_chooser(log, MESSAGE)
    run_with_keys(chooser, "/d link\rq")
    assert chooser.search_string == "d link"
    assert chooser.search is False
    assert only_opened(log, [])

    log2 = tmp_path / "opened2"
    run_with_keys(make_chooser(log2, MESSAGE), "/d link\rj\rq")
    assert only_opened(log2, [SECOND])


def test_enter_on_no_matches_restores_list(tmp_path):
    """Enter on a search with no matches drops the search and shows every URL
    again, rather than leaving an empty list.

    """
    chooser = make_chooser(tmp_path / "opened", MESSAGE)
    run_with_keys(chooser, "/zzzz\rq")
    assert chooser.search is False
    assert chooser.search_string == ""
    assert chooser.items == chooser.items_orig


# Keys that move focus or read it, which crashed on the empty list a
# no-match search used to leave. F1 opens the help menu, which the first q
# closes; the second q quits.
@pytest.mark.parametrize("key", ["J", "K", "g", "G", "c", "R", "s", "a",
                                 "2", "\x1bOP"],
                         ids=["J", "K", "g", "G", "c", "R", "s", "a",
                              "2", "F1"])
def test_keys_after_no_match_search(tmp_path, key):
    chooser = make_chooser(tmp_path / "opened", MESSAGE)
    run_with_keys(chooser, ["/zzzz\r", key, "q", "q"])
