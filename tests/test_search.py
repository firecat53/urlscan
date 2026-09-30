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


def highlighted(chooser):
    """True if any context text shows search highlighting."""
    return any(attr == 'search' for item in chooser.items
               if hasattr(item, 'attrib') for attr, _ in item.attrib)


@pytest.mark.parametrize("keys", [
    ["/Second", "\x1b", "q"],          # while typing
    ["/zzzz", "\x1b", "q"],            # while typing, no matches
    ["/Second\r", "\x1b", "q"],        # after Enter, results showing
], ids=["typing", "no_matches", "after_enter"])
def test_esc_clears_search(tmp_path, keys):
    chooser = make_chooser(tmp_path / "opened", MESSAGE)
    run_with_keys(chooser, keys)
    assert chooser.search is False
    assert chooser.search_string == ""
    assert chooser.items == chooser.items_orig
    assert not highlighted(chooser)
    footer = chooser.top.base_widget.footer
    assert footer.base_widget.text == ""


def test_esc_without_search_does_nothing(tmp_path):
    """Esc with no search doesn't touch the list, so compact mode stays."""
    chooser = make_chooser(tmp_path / "opened", MESSAGE)
    run_with_keys(chooser, ["c", "\x1b", "q"])
    assert chooser.compact is True
    assert chooser.items == chooser.rows


def test_question_mark_is_typed_into_search(tmp_path):
    """While searching, ? is part of the search, not the help key."""
    message = f"Subject: test\n\nWhat? {FIRST}\n"
    chooser = make_chooser(tmp_path / "opened", message)
    run_with_keys(chooser, ["/what?\r", "q"])
    assert chooser.search_string == "what?"
    assert chooser.help_menu is False


@pytest.mark.parametrize("key", ["\x1b[A", "\x1b[H"], ids=["up", "home"])
def test_up_and_home_are_not_typed_into_search(tmp_path, key):
    chooser = make_chooser(tmp_path / "opened", MESSAGE)
    run_with_keys(chooser, ["/Sec", key, "ond\r", "q"])
    assert chooser.search_string == "Second"
