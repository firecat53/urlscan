"""Baseline tests for scanning a message into URLs and their context.

These describe what urlscan does today, so that later changes have something
to move against.
"""

import pytest

from urlscan import urlscan

from conftest import ALL_PATHS, FIXTURE_PATHS, group_urls, scan, unit_text


def fixture(name):
    return next(p for p in FIXTURE_PATHS if p.name == name)


@pytest.mark.parametrize('path', ALL_PATHS, ids=lambda p: p.name)
def test_every_message_can_be_scanned(path):
    """Whatever the encoding or markup, scanning a message must not raise."""
    scan(path)


@pytest.mark.parametrize('path', ALL_PATHS, ids=lambda p: p.name)
def test_every_group_holds_at_least_one_url(path):
    """Context is extracted around URLs, so a group without one is a bug."""
    for group, _, _ in scan(path):
        assert any(chunk.url is not None for unit in group for chunk in unit)


@pytest.mark.parametrize('path', ALL_PATHS, ids=lambda p: p.name)
def test_every_url_is_a_non_empty_string(path):
    for url in group_urls(scan(path)):
        assert isinstance(url, str) and url


@pytest.mark.parametrize('path', ALL_PATHS, ids=lambda p: p.name)
def test_chunk_markup_is_text_a_styled_pair_or_nothing(path):
    """The shape urlchoose.process_urls and chunk_text both rely on."""
    for group, _, _ in scan(path):
        for unit in group:
            for chunk in unit:
                markup = chunk.markup
                assert markup is None or isinstance(markup, (str, tuple))
                if isinstance(markup, tuple):
                    attr, text = markup
                    assert isinstance(attr, str) and isinstance(text, str)


def test_urls_are_found_in_the_order_they_appear():
    """Schemes urlscan knows, and bare addresses turned into mailto: links."""
    assert group_urls(scan(fixture('links'))) == [
        'http://google.com',
        'https://google.com',
        'ftp://google.com',
        'http://www.google.com/?action=!input.joe=98765432',
        'mailto:someuser4153@gmail.com',
        'mailto:joe@joe.com',
    ]


def test_a_plain_text_url_shows_as_a_placeholder():
    """A URL with no text of its own is drawn as <URL> by process_urls."""
    (group, _, _), *_ = urlscan.extracturls('see http://example.com now\n')
    assert [unit_text(unit) for unit in group] == ['see <URL> now', '']


def test_context_is_one_line_either_side_of_the_url():
    groups = urlscan.extracturls('A\nB\nC\nsee http://example.com\nD\nE\n')
    (group, usedfirst, usedlast), = groups
    assert [unit_text(unit) for unit in group] == ['C', 'see <URL>', 'D']
    assert not usedfirst and not usedlast


def test_nearby_urls_share_one_group():
    """A gap of two lines is the context of both, so the groups merge; a gap
    of three leaves a line belonging to neither, and they stay apart."""
    merged = urlscan.extracturls('http://a.example.com\nD\nX\nhttp://b.example.com\n')
    (group, _, _), = merged
    assert [unit_text(unit) for unit in group] == \
        ['<URL>', 'D', 'X', '<URL>', '']
    split = urlscan.extracturls(
        'http://a.example.com\nD\nX\nY\nhttp://b.example.com\n')
    assert [[unit_text(unit) for unit in group] for group, _, _ in split] == \
        [['<URL>', 'D'], ['Y', '<URL>', '']]
