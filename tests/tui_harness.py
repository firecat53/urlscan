"""Run URLChooser's real urwid main loop on a pseudo-terminal and type keys
into it, so tests exercise the same path as a user in mutt or tmux.

Links are 'opened' by a --run-safe command that appends each URL to a log
file, so tests can check what was opened.

"""

from email import policy
from email.parser import BytesParser
import fcntl
from pathlib import Path
import os
import pty
import signal
import struct
import sys
import termios
import threading
import time

import pytest
import urwid

# Test against the working tree rather than any installed copy of urlscan.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from urlscan import urlchoose, urlscan  # noqa: E402

URLS = ["https://one.example.com/a", "https://two.example.com/b"]
MESSAGE = f"Subject: test\n\nFirst {URLS[0]} and second {URLS[1]}\n"

# Pause between chunks of keys. It must exceed urwid's escape-sequence wait
# (Screen.complete_wait, 0.125s), or a lone Esc followed by a key is read as
# one meta-key.
CHUNK_PAUSE = 0.3

# How long a test may wait for the main loop to exit before failing.
TIMEOUT = 10


class LoopTimeout(Exception):
    """The main loop did not exit in time."""


def make_chooser(log, message=MESSAGE, **kwargs):
    """Build a URLChooser for `message` whose links are 'opened' by appending
    them to the file `log`.

    """
    msg = BytesParser(policy=policy.default.clone(utf8=True)).parsebytes(
        message.encode())
    runsafe = f"sh -c 'echo \"$0\" >> {log}' {{}}"
    return urlchoose.URLChooser(urlscan.msgurls(msg), runsafe=runsafe, **kwargs)


def opened(log):
    """URLs written to `log` by the runsafe command, in order."""
    return log.read_text().split() if log.exists() else []


def wait_for(condition, timeout=TIMEOUT):
    """Poll until condition() is true. Returns whether it became true."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if condition():
            return True
        time.sleep(0.02)
    return False


def only_opened(log, expected):
    """True if `expected` is opened and nothing else follows shortly after."""
    if not wait_for(lambda: opened(log) == expected):
        return False
    time.sleep(0.3)
    return opened(log) == expected


def run_with_keys(chooser, keys):
    """Run chooser.main() on a pty, typing `keys` once the screen is up.

    `keys` is a string, or a list of strings typed with a pause between them.
    urwid reads keys typed together as one batch, so use a list when a key's
    effect must land before the next key arrives (closing the help menu
    discards the rest of its batch, for example).

    Raises LoopTimeout if main() doesn't return within TIMEOUT seconds.

    """
    chunks = [keys] if isinstance(keys, str) else keys
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0))
    term_in = os.fdopen(slave, "r", closefd=False)
    term_out = os.fdopen(os.dup(slave), "w")
    chooser.tui = urwid.raw_display.Screen(input=term_in, output=term_out)
    finished = threading.Event()

    def drain():
        # Keep reading the screen output so urwid never blocks writing it.
        # Ends with EIO once every slave fd is closed.
        try:
            while os.read(master, 65536):
                pass
        except OSError:
            pass

    def type_keys():
        # Keys typed before urwid puts the terminal in raw mode would sit in
        # the line discipline waiting for a newline.
        if wait_for(lambda: finished.is_set()
                    or not termios.tcgetattr(slave)[3] & termios.ICANON):
            for chunk in chunks:
                if finished.is_set():
                    break
                os.write(master, chunk.encode())
                time.sleep(CHUNK_PAUSE)

    def on_alarm(_signum, _frame):
        raise LoopTimeout(f"main loop still running after {TIMEOUT}s")

    helpers = [threading.Thread(target=drain, daemon=True),
               threading.Thread(target=type_keys, daemon=True)]
    for thread in helpers:
        thread.start()
    old = signal.signal(signal.SIGALRM, on_alarm)
    signal.alarm(TIMEOUT)
    try:
        chooser.main()
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)
        # Stop the helpers before closing master and slave: a helper still
        # using a closed fd number could hit a file the test opens next and
        # steal its contents.
        finished.set()
        helpers[1].join()
        term_in.close()
        term_out.close()
        os.close(slave)
        helpers[0].join()
        os.close(master)


@pytest.fixture(autouse=True)
def gui_browser(monkeypatch):
    """Take the threaded (non text-mode browser) path when opening links."""
    monkeypatch.setenv("BROWSER", "firefox")
