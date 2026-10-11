"""Tests for how extracted context is drawn, via URLChooser.process_urls.

These render the urwid widgets the browser would show and look at the result,
so they catch problems that only appear on screen.
"""

import pytest
import urwid

from urlscan import urlchoose
from urlscan.urlscan import Chunk

from conftest import ALL_PATHS, FIXTURE_PATHS, group_urls, scan


def chooser(extracted, whitespaceoff=False, dedupe=False):
    return urlchoose.URLChooser(extracted, whitespaceoff=whitespaceoff,
                                dedupe=dedupe)


def context_widgets(uc):
    """The Text widgets holding context, one per group."""
    return [item for item in uc.items if isinstance(item, urwid.Text)]


def rows(widget, width):
    """What the widget draws at `width` columns, one string per row."""
    return [row.decode().rstrip() for row in widget.render((width,)).text]


def group(*units):
    """A single extracted group, in the shape process_urls expects."""
    return [(list(units), True, True)]


# --- nothing may go missing on screen --------------------------------------

def test_empty_chunk_between_styles_does_not_cut_the_row_short():
    """Regression: urwid stops drawing a row at a zero-length run lying
    between two differently styled ones. The HTML parser emits empty chunks,
    so a bold heading followed by one used to swallow the rest of the row."""
    uc = chooser(group([Chunk(('msgtext:bold', 'Heading '), None),
                        Chunk(('msgtext', ''), None),
                        Chunk(('anchor', 'the link'), 'http://example.com'),
                        Chunk(('msgtext', ' and what follows'), None)]),
                 whitespaceoff=True)
    (widget,) = context_widgets(uc)
    assert rows(widget, 80)[0] == 'Heading the link [1] and what follows'


@pytest.mark.parametrize('path', ALL_PATHS, ids=lambda p: p.name)
def test_every_character_of_context_reaches_the_screen(path):
    """Whatever process_urls builds, urwid must draw all of it.

    Compared with whitespace removed, since wrapping moves spaces about.
    Before empty chunks were dropped, some HTML mail lost hundreds of
    characters this way.
    """
    for whitespaceoff in (False, True):
        uc = chooser(scan(path), whitespaceoff)
        for widget in context_widgets(uc):
            wanted = ''.join(widget.get_text()[0].split())
            drawn = ''.join(''.join(rows(widget, 150)).split())
            assert drawn == wanted, f'-W={whitespaceoff}'


# --- joining lines ---------------------------------------------------------

def test_whitespace_off_keeps_words_from_neighbouring_lines_apart():
    """Regression: lines used to be joined with nothing between them, so the
    last word of one ran straight into the first word of the next."""
    uc = chooser(group([Chunk('The Secret List', None)],
                       [Chunk('Having trouble? ', None),
                        Chunk(None, 'http://example.com')]),
                 whitespaceoff=True)
    (widget,) = context_widgets(uc)
    assert widget.get_text()[0].startswith('The Secret List Having trouble?')


def test_whitespace_off_adds_no_space_where_the_text_has_one():
    uc = chooser(group([Chunk('ends with a space ', None)],
                       [Chunk('starts plain ', None),
                        Chunk(None, 'http://example.com')]),
                 whitespaceoff=True)
    (widget,) = context_widgets(uc)
    assert widget.get_text()[0].startswith('ends with a space starts plain')


# --- the URL list ----------------------------------------------------------

@pytest.mark.parametrize('path', ALL_PATHS, ids=lambda p: p.name)
def test_the_button_list_matches_the_urls_that_were_found(path):
    """The URL list drives the buttons, their numbering and --no-browser."""
    assert chooser(scan(path)).urls == group_urls(scan(path))


@pytest.mark.parametrize('path', ALL_PATHS, ids=lambda p: p.name)
def test_dedupe_keeps_the_first_of_each_url_in_order(path):
    found = group_urls(scan(path))
    unique = list(dict.fromkeys(found))
    assert chooser(scan(path), dedupe=True).urls == unique
