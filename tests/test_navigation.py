"""Moving focus through the list, and keeping it across view changes."""

import pytest
import urwid

from tui_harness import gui_browser, make_chooser, run_with_keys  # noqa: F401

A, B, C, D = (f"https://{x}.example.com/{n}" for x, n in zip("abcd", "1234"))
FILLER = "\n".join(f"filler line {i}" for i in range(8))
# Three context groups: A alone, B and C together, D alone.
MESSAGE = (f"Subject: test\n\nAlpha {A}\n\n{FILLER}\n\n"
           f"Beta {B} and {C}\n\n{FILLER}\n\nGamma {D}\n")


def focused_url(chooser):
    """The URL shown on the focused row."""
    row = chooser.top.base_widget.body.focus
    return row[1].base_widget.label


def shown_urls(chooser):
    """The URLs the list shows, in order."""
    return [i[1].base_widget.label for i in chooser.items
            if isinstance(i, urwid.Columns)]


def run(tmp_path, keys):
    # The test terminal is narrow; keep labels whole so they can be compared.
    chooser = make_chooser(tmp_path / "opened", MESSAGE, shorten=False)
    run_with_keys(chooser, keys)
    return chooser


@pytest.mark.parametrize("keys, expected", [
    ("q", A),        # starts on the first URL, not the context above it
    ("Gq", D),       # bottom
    ("Ggq", A),      # top
    # j and k scroll through tall context before moving focus, so test them
    # with context hidden (c), where URLs are adjacent.
    ("cjq", B),      # down
    ("cjjkq", B),    # up
    ("cjj\x1b[Aq", B),   # up arrow
    ("G\x1b[Hq", A),     # home
    ("Jq", B),       # next URL
    ("JJq", C),
    ("GKq", C),      # previous URL
    ("KKq", A),      # previous stops at the first URL
    ("GJq", D),      # next stops at the last URL
    ("3q", C),       # jump to URL number
])
def test_move_focus(tmp_path, keys, expected):
    assert focused_url(run(tmp_path, keys)) == expected


@pytest.mark.parametrize("keys, expected", [
    ("Jcq", B),      # context off
    ("Jccq", B),     # and back on
    ("cGcq", D),
])
def test_context_toggle_keeps_focus(tmp_path, keys, expected):
    assert focused_url(run(tmp_path, keys)) == expected


def test_context_toggle_shows_only_urls(tmp_path):
    chooser = run(tmp_path, "cq")
    assert all(isinstance(i, urwid.Columns) for i in chooser.items)
    assert shown_urls(chooser) == [A, B, C, D]


@pytest.mark.parametrize("help_key", ["\x1bOP", "?"], ids=["F1", "?"])
def test_help_menu_keeps_focus(tmp_path, help_key):
    # Help opens; any key closes it (and is otherwise ignored).
    chooser = run(tmp_path, ["JJ", help_key, "x", "q"])
    assert focused_url(chooser) == C
    assert shown_urls(chooser) == [A, B, C, D]


@pytest.mark.parametrize("help_key", ["\x1bOP", "?"], ids=["F1", "?"])
def test_help_key_opens_help(tmp_path, help_key):
    # With help open, g only closes it, so focus stays at the bottom.
    # Without help, g would move focus to the top.
    chooser = run(tmp_path, ["G", help_key, "g", "q"])
    assert focused_url(chooser) == D
    assert chooser.help_menu is False


@pytest.mark.parametrize("keys, shown, expected", [
    ("/Beta\rq", [B, C], B),
    ("/Gamma\rq", [D], D),
    ("/Beta\rjq", [B, C], C),
])
def test_search_focuses_first_match(tmp_path, keys, shown, expected):
    chooser = run(tmp_path, keys)
    assert shown_urls(chooser) == shown
    assert focused_url(chooser) == expected


@pytest.mark.parametrize("keys, shown, expected", [
    ("Rq", [D, C, B, A], A),       # focus stays on the same URL
    ("JRq", [D, C, B, A], B),
    ("GRq", [D, C, B, A], D),
    ("JcRq", [D, C, B, A], B),     # compact
    ("cGRq", [D, C, B, A], D),
    ("JRcq", [D, C, B, A], B),     # context toggle keeps the reversal
    ("JRccq", [D, C, B, A], B),
    ("cRcq", [D, C, B, A], A),
    ("JRRq", [A, B, C, D], B),     # and back
    ("cJRcRq", [A, B, C, D], B),
])
def test_reverse(tmp_path, keys, shown, expected):
    chooser = run(tmp_path, keys)
    assert shown_urls(chooser) == shown
    assert focused_url(chooser) == expected


def test_reverse_keeps_context_above_urls(tmp_path):
    chooser = run(tmp_path, "Rq")
    kinds = [type(i).__name__ for i in chooser.items]
    assert kinds == ["Divider", "Text", "URLRow",
                     "Divider", "Text", "URLRow", "URLRow",
                     "Divider", "Text", "URLRow"]


@pytest.mark.parametrize("keys, expected", [
    ("Rc3q", C),     # numbers go to the URL labelled [n], whatever the order
    ("R1q", A),
    ("R4q", D),
    ("c9q", A),      # no URL 9: ignored
])
def test_number_jump(tmp_path, keys, expected):
    assert focused_url(run(tmp_path, keys)) == expected


def test_start_reversed(tmp_path):
    chooser = make_chooser(tmp_path / "opened", MESSAGE, shorten=False, reverse=True)
    run_with_keys(chooser, "q")
    assert shown_urls(chooser) == [D, C, B, A]
    assert focused_url(chooser) == D
