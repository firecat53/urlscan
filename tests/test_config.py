"""Palettes and keybindings from ~/.config/urlscan/config.json, and --genconf."""

import json

import pytest

import tui_harness  # noqa: F401  (puts the working tree on sys.path)
from urlscan import urlchoose

BUILTIN_PALETTES = ["default", "bw", "catppuccin"]


@pytest.fixture(autouse=True)
def conf(tmp_path, monkeypatch):
    """Point ~ at an empty directory; return where config.json would go."""
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path / ".config" / "urlscan" / "config.json"


def write_config(conf, data):
    conf.parent.mkdir(parents=True)
    conf.write_text(json.dumps(data))


def action(chooser, key):
    return chooser.keys[key].__name__.lstrip("_")


def test_no_config_uses_builtins():
    chooser = urlchoose.URLChooser([])
    assert list(chooser.palettes) == BUILTIN_PALETTES
    assert action(chooser, "enter") == "open_url"
    assert action(chooser, "j") == "down"
    assert action(chooser, "7") == "digits"


def test_config_palettes_replace_builtins(conf):
    palette = [["header", "black", "white", "", "", ""]]
    write_config(conf, {"palettes": {"mine": palette}})
    chooser = urlchoose.URLChooser([])
    assert chooser.palettes == {"mine": [tuple(palette[0])]}


def test_empty_config_palettes_keep_builtins(conf):
    write_config(conf, {"palettes": {}})
    assert list(urlchoose.URLChooser([]).palettes) == BUILTIN_PALETTES


def test_config_keys(conf):
    write_config(conf, {"keys": {"x": "open_url", "j": "up", "enter": "",
                                 "not_a_default": ""}})
    chooser = urlchoose.URLChooser([])
    assert action(chooser, "x") == "open_url"
    assert action(chooser, "j") == "up"
    assert "enter" not in chooser.keys
    assert action(chooser, "k") == "up"     # untouched defaults remain


def test_genconf_writes_defaults(conf, capsys):
    urlchoose.URLChooser([], genconf=True)
    data = json.loads(conf.read_text())
    assert list(data["palettes"]) == BUILTIN_PALETTES
    assert data["keys"]["enter"] == "open_url"
    assert data["keys"]["J"] == "next"
    assert data["keys"]["5"] == "digits"
    assert "Created" in capsys.readouterr().out
    # The generated file loads back to the same bindings and palettes.
    chooser = urlchoose.URLChooser([])
    assert list(chooser.palettes) == BUILTIN_PALETTES
    assert {k: action(chooser, k) for k in chooser.keys} == data["keys"]


def test_genconf_keeps_existing_config(conf, capsys):
    write_config(conf, {"keys": {"x": "quit"}})
    urlchoose.URLChooser([], genconf=True)
    assert json.loads(conf.read_text()) == {"keys": {"x": "quit"}}
    assert "already exists" in capsys.readouterr().out
