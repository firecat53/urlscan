"""Tests for resolving reference-style links to the prose that mentions them.

Text converted from HTML keeps its links as a footnote block: a marker where
the link sat, and the URLs collected at the end. The line holding the URL then
says nothing about it, so urlscan rebuilds that line from the prose around the
marker. See urlscan.resolve_reference_links.

The fixtures were generated from tests/fixtures/refs_source.html with the
converters mutt users actually run:

    lynx -dump -width=72                            -> refs_lynx
    w3m -dump -cols 72 -o display_link_number=1     -> refs_w3m
    pandoc -f html -t markdown --reference-links --columns=72 -> refs_pandoc

refs_markdown is the sample from issue #162.
"""

import pytest

from urlscan import urlscan

from conftest import ALL_PATHS, FIXTURE_PATHS, group_urls, scan, unit_text

REFS_FIXTURES = ['refs_markdown', 'refs_lynx', 'refs_w3m', 'refs_pandoc']

# Two of the messages collected long before any of this turned out to carry
# footnote blocks of their own, which is a fair sign of how common they are.
FOOTNOTE_FIXTURES = REFS_FIXTURES + ['outgoing.msg', 'test_2']


def fixture(name):
    return next(p for p in FIXTURE_PATHS if p.name == name)


def context_lines(source):
    """Every context line of a message, whether a path or the text itself."""
    groups = (scan(source) if hasattr(source, 'name')
              else urlscan.extracturls(source))
    return [unit_text(unit) for group, _, _ in groups for unit in group]


def unresolved(source):
    """The same, with reference resolution switched off."""
    real = urlscan.resolve_reference_links
    urlscan.resolve_reference_links = lambda lines, linechunks: linechunks
    try:
        return context_lines(source)
    finally:
        urlscan.resolve_reference_links = real


# --- the four converters ---------------------------------------------------

def test_markdown_definitions_show_the_prose_around_the_marker():
    """The case reported in issue #162."""
    lines = context_lines(fixture('refs_markdown'))
    assert 'This is a sample test <URL> to show ' in lines
    assert 'the folding in urlscan <URL>, could be' in lines
    assert 'character <URL> near the linked' in lines
    # Nothing is left of the footnote block itself.
    assert not [line for line in lines if line.startswith('[1]: ')]


@pytest.mark.parametrize('name', ['refs_lynx', 'refs_w3m'])
def test_a_references_section_is_resolved(name):
    lines = ' '.join(context_lines(fixture(name)))
    assert 'so the <URL> migration guide' in lines
    assert 'release cadence in <URL> the forum thread' in lines


def test_the_same_url_twice_keeps_a_context_for_each():
    """lynx and w3m number each occurrence, so each gets its own prose."""
    lines = ' '.join(context_lines(fixture('refs_lynx')))
    assert 'so the <URL> migration guide is now' in lines
    assert '<URL> migration guide covers that too' in lines


def test_pandoc_word_labels_are_resolved():
    lines = ' '.join(context_lines(fixture('refs_pandoc')))
    assert 'so the <URL> is now the' in lines


def test_a_label_wrapped_across_lines_is_left_alone():
    """pandoc wraps '[the recap\\npage]', so that marker cannot be found and
    the definition line stays as it was."""
    lines = context_lines(fixture('refs_pandoc'))
    assert '  [the recap page]: <URL>' in lines


# --- what must not change --------------------------------------------------

@pytest.mark.parametrize('path', ALL_PATHS, ids=lambda p: p.name)
def test_the_urls_found_are_the_same_either_way(path):
    """Resolution rewrites context, never the URL list its numbering drives."""
    real = urlscan.resolve_reference_links
    urlscan.resolve_reference_links = lambda lines, linechunks: linechunks
    try:
        baseline = group_urls(scan(path))
    finally:
        urlscan.resolve_reference_links = real
    assert group_urls(scan(path)) == baseline


@pytest.mark.parametrize('path', ALL_PATHS, ids=lambda p: p.name)
def test_messages_without_a_footnote_block_are_untouched(path):
    if path.name in FOOTNOTE_FIXTURES:
        pytest.skip('this one has a footnote block')
    assert context_lines(path) == unresolved(path)


def test_a_w3m_footnote_in_real_mail_is_resolved():
    """outgoing.msg, collected years before this feature existed."""
    assert 'Cela ressemble à un excellent recipie <URL> déjeuner.' \
        in context_lines(fixture('outgoing.msg'))


def test_a_lynx_references_section_in_real_mail_is_resolved():
    """test_2, likewise. Its link text is the URL itself, so the prose keeps
    it: lynx writes '[1]http://...' when a link has no other text."""
    lines = context_lines(fixture('test_2'))
    assert any(line.strip().startswith('<URL> http://www.meetup.com/')
               for line in lines)


def test_a_label_defined_twice_in_real_mail_is_left_alone():
    """test_2 numbers two different mailto: links '2.', so neither resolves."""
    assert '   2. <URL>' in context_lines(fixture('test_2'))


def test_a_url_written_out_in_the_prose_is_not_found_twice():
    """The prose is carried over as text, not rescanned."""
    message = ('Mirror at http://mirror.example.com or the [1] guide.\n'
               '\n'
               '[1]: http://example.com/guide\n')
    assert group_urls(urlscan.extracturls(message)) == [
        'http://mirror.example.com', 'http://example.com/guide']
    assert 'Mirror at http://mirror.example.com or the <URL> guide.' \
        in context_lines(message)


def test_a_definition_holding_two_urls_is_left_alone():
    """A single token can still be two URLs -- two addresses separated by a
    comma. Substituting such a line would drop one from the list."""
    message = ('Write to [1] either of them.\n'
               '\n'
               '[1]: a@example.com,b@example.com\n')
    assert group_urls(urlscan.extracturls(message)) == [
        'mailto:a@example.com', 'mailto:b@example.com']
    assert context_lines(message) == unresolved(message)


def test_a_numbered_list_is_not_a_footnote_block():
    """'1. url' only counts under a References heading; on its own it is an
    ordinary numbered list, and [1] elsewhere may mean anything."""
    message = ('Step [1] comes first.\n'
               '\n'
               '   1. http://example.com/one\n')
    assert context_lines(message) == unresolved(message)


def test_a_numbered_list_under_a_references_heading_is_resolved():
    message = ('Step [1] comes first.\n'
               '\n'
               'References\n'
               '\n'
               '   1. http://example.com/one\n')
    assert 'Step <URL> comes first.' in context_lines(message)


def test_a_label_defined_twice_is_left_alone():
    message = ('See the [1] guide.\n'
               '\n'
               '[1]: http://example.com/one\n'
               '[1]: http://example.com/two\n')
    assert context_lines(message) == unresolved(message)


def test_a_definition_with_no_marker_is_left_alone():
    message = 'Nothing refers to it.\n\n[1]: http://example.com/one\n'
    assert '[1]: <URL>' in context_lines(message)


# --- how the substituted line reads ----------------------------------------

def test_a_marker_before_its_link_text_gains_a_space():
    message = 'Read the [1]migration guide now.\n\n[1]: http://example.com\n'
    assert 'Read the <URL> migration guide now.' in context_lines(message)


def test_a_marker_before_punctuation_does_not():
    message = 'Read the guide [1], then upgrade.\n\n[1]: http://example.com\n'
    assert 'Read the guide <URL>, then upgrade.' in context_lines(message)
