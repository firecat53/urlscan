"""Opening, queueing and relabelling the URL with focus.

Each row carries its own URL, and open_url is an ordinary keybinding, so
every action works on the URL the user sees.

"""

import json

import pytest

from tui_harness import gui_browser, make_chooser, only_opened, run_with_keys  # noqa: F401

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


DUP = "https://dup.example.com/x"
# The same URL twice. Without --dedupe it gets two rows, [1] and [2].
DUP_MESSAGE = f"Subject: test\n\nFirst {DUP} and again {DUP} and {SECOND}\n"


def labels(chooser):
    return [row.button.label for row in chooser.rows]


@pytest.mark.parametrize("keys", [
    "aJaKdJdq",     # add both, delete both, one at a time
    "aJaKdq",       # add both, delete from the first
    "aJadq",        # add both, delete from the second
    "aJdq",         # add one, delete from its duplicate
])
def test_duplicate_urls_share_queued_marker(tmp_path, keys):
    chooser = make_chooser(tmp_path / "opened", DUP_MESSAGE, shorten=False)
    run_with_keys(chooser, keys)
    assert chooser.queue == []
    assert labels(chooser) == [DUP, DUP, SECOND]


def test_adding_a_duplicate_marks_every_copy(tmp_path):
    chooser = make_chooser(tmp_path / "opened", DUP_MESSAGE, shorten=False)
    run_with_keys(chooser, "aq")
    assert chooser.queue == [DUP]
    assert labels(chooser) == ["* " + DUP, "* " + DUP, SECOND]
