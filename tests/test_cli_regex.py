"""CLI tests for --regex validation.

An invalid regular expression passed via --regex/--E must be rejected with
a clean argparse usage error (exit code 2), not an unhandled `re.error`
traceback from deep inside the URL extraction code.
"""

import sys

import pytest

from urlscan.__main__ import parse_arguments


def test_invalid_regex_exits_with_usage_error(monkeypatch, capsys):
    monkeypatch.setattr(
        sys, "argv", ["urlscan", "--regex", "(unclosed", "somefile"]
    )
    with pytest.raises(SystemExit) as exc_info:
        parse_arguments()
    assert exc_info.value.code == 2
    _, err = capsys.readouterr()
    assert "invalid" in err.lower()


def test_valid_regex_is_accepted(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["urlscan", "-n", "--regex", r"https?://\S+", "somefile"],
    )
    args = parse_arguments()
    assert args.regex == r"https?://\S+"
