"""Opening, queueing and relabelling the URL with focus.

Each row carries its own URL, and open_url is an ordinary keybinding, so
every action works on the URL the user sees.

"""

import json
import time

import pytest

from tui_harness import gui_browser, make_chooser, opened, run_with_keys, wait_for  # noqa: F401

ESCAPED = "https://one.example.com/a\\_b"
UNESCAPED = "https://one.example.com/a_b"
SECOND = "https://two.example.com/b"
MESSAGE = f"Subject: test\n\nFirst link {ESCAPED}\n\nSecond link {SECOND}\n"


@pytest.fixture(autouse=True)
def config_home(tmp_path, monkeypatch):
    """Point ~ at an empty directory, so a real config.json can't interfere."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


def write_config(home, keys):
    conf = home / ".config" / "urlscan" / "config.json"
    conf.parent.mkdir(parents=True)
    conf.write_text(json.dumps({"keys": keys}))


def only_opened(log, expected):
    """True if `expected` is opened and nothing else follows shortly after."""
    if not wait_for(lambda: opened(log) == expected):
        return False
    time.sleep(0.3)
    return opened(log) == expected


@pytest.mark.parametrize("key", ["\r", " "])
def test_enter_and_space_open_focused_url(tmp_path, key):
    log = tmp_path / "opened"
    run_with_keys(make_chooser(log, MESSAGE), "j" + key + "q")
    assert only_opened(log, [SECOND])


def test_open_after_unescape_opens_unescaped_url(tmp_path):
    """After u, Enter opens the URL as shown, not the escaped original."""
    log = tmp_path / "opened"
    # The test terminal is narrow; keep labels whole so they can be compared.
    chooser = make_chooser(log, MESSAGE, shorten=False)
    run_with_keys(chooser, "u\rq")
    assert only_opened(log, [UNESCAPED])
    assert chooser.rows[0].button.label == UNESCAPED


def test_queue_uses_unescaped_url(tmp_path):
    chooser = make_chooser(tmp_path / "opened", MESSAGE)
    run_with_keys(chooser, "uaq")
    assert chooser.queue == [UNESCAPED]


def test_queue_marker_survives_relabelling(tmp_path):
    """a marks the row as queued; S and u relabel it without losing the mark."""
    chooser = make_chooser(tmp_path / "opened", MESSAGE)
    run_with_keys(chooser, "aSuq")
    assert chooser.rows[0].button.label == "* " + UNESCAPED
    assert chooser.rows[1].button.label == SECOND


def test_open_url_can_be_rebound(tmp_path, config_home):
    """Config can bind open_url to another key and unbind Enter. Unbinding a
    key that has no default binding doesn't stop later bindings loading.

    """
    write_config(config_home, {"zz": "", "x": "open_url", "enter": ""})
    log = tmp_path / "opened"
    # Enter on the first URL does nothing; x on the second opens it.
    run_with_keys(make_chooser(log, MESSAGE), "\rjxq")
    assert only_opened(log, [SECOND])


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
