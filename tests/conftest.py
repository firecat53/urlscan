"""Shared fixtures and helpers for the urlscan test suite."""

from email import policy
from email.parser import BytesParser
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = Path(__file__).resolve().parent / 'fixtures'
EMAIL_DIR = REPO_ROOT / 'test_emails'

# Test against the working tree rather than any installed copy of urlscan.
sys.path.insert(0, str(REPO_ROOT))

from urlscan import urlscan  # noqa: E402

# The committed corpus: synthetic messages plus real ones that have been
# de-identified (names, addresses and company domains replaced, preserving the
# label count and TLD validity of every host so urlscan still finds exactly the
# same URLs). Everything asserted exactly lives here, so the suite is self
# contained.
FIXTURE_PATHS = sorted(p for p in FIXTURE_DIR.iterdir() if p.is_file())

# test_emails/ is a developer's own scratch pile of real messages. It is
# gitignored, so it is usually absent and its contents differ from machine to
# machine; tests over it therefore assert only properties that must hold for
# any input -- never counts or exact text.
EMAIL_PATHS = (sorted(p for p in EMAIL_DIR.iterdir() if p.is_file())
               if EMAIL_DIR.is_dir() else [])

# Every message available to the suite.
ALL_PATHS = FIXTURE_PATHS + EMAIL_PATHS


def parse_email(path):
    """Parse a message file into an EmailMessage."""
    with open(path, 'rb') as fobj:
        return BytesParser(policy=policy.default.clone(utf8=True)).parse(fobj)


def unit_text(unit):
    """Render one context unit (a list of Chunks) to plain text.

    Mirrors how urlchoose.process_urls displays a unit: a URL chunk with no
    markup of its own shows as '<URL>', anything else shows its text.

    """
    out = []
    idx = 0
    while idx < len(unit):
        chunk = unit[idx]
        if chunk.url is None:
            out.append(urlscan.chunk_text(chunk))
            idx += 1
            continue
        # Adjacent chunks sharing a URL render as a single entry.
        text = []
        url = chunk.url
        while idx < len(unit) and unit[idx].url == url:
            text.append(urlscan.chunk_text(unit[idx]))
            idx += 1
        out.append(''.join(text) or '<URL>')
    return ''.join(out)


def group_text(group):
    """Render a whole context group to text, one line per unit."""
    return '\n'.join(unit_text(unit) for unit in group)


def group_urls(groups):
    """Flatten extracted groups into the URL list, in display order."""
    return [chunk.url.strip()
            for group, _, _ in groups
            for unit in group
            for chunk in unit
            if chunk.url is not None]


def scan(path, **kwargs):
    """Extract context groups from a test email."""
    return list(urlscan.msgurls(parse_email(path), **kwargs))
