"""URL opening runs in worker threads; the UI must still quit and redraw."""

import os
import signal
import threading
import time

from tui_harness import (URLS, gui_browser, make_chooser, opened,  # noqa: F401
                         run_with_keys, wait_for)


def test_single_quits_after_opening_url(tmp_path):
    """--single: Enter opens the URL in a worker thread, then urlscan exits."""
    log = tmp_path / "opened"
    chooser = make_chooser(log, single=True)
    run_with_keys(chooser, "\r")
    assert wait_for(lambda: opened(log) == URLS[:1])


def test_single_opens_whole_queue_then_quits(tmp_path):
    """--single with the queue: every queued URL opens before urlscan exits."""
    log = tmp_path / "opened"
    chooser = make_chooser(log, single=True)
    # Queue both URLs, then open the queue.
    run_with_keys(chooser, "aja" + "o")
    assert sorted(opened(log)) == sorted(URLS)


def test_queue_opens_every_url_and_keeps_running(tmp_path):
    """Without --single, opening the queue opens every URL and urlscan keeps
    running until the user quits.

    """
    log = tmp_path / "opened"
    chooser = make_chooser(log)
    returned = threading.Event()
    running_after_open = []

    def quit_once_opened():
        if wait_for(lambda: len(opened(log)) == len(URLS)):
            # Give the redraw request time to reach the main loop.
            time.sleep(0.3)
            running_after_open.append(not returned.is_set())
            os.kill(os.getpid(), signal.SIGUSR1)

    # 'q' can't be typed up front: it would quit before the queue opens. Quit
    # from the main thread once both URLs are logged instead.
    def on_usr1(_signum, _frame):
        chooser._quit()

    old = signal.signal(signal.SIGUSR1, on_usr1)
    threading.Thread(target=quit_once_opened, daemon=True).start()
    try:
        run_with_keys(chooser, "aja" + "o")
    finally:
        returned.set()
        signal.signal(signal.SIGUSR1, old)
    assert sorted(opened(log)) == sorted(URLS)
    assert running_after_open == [True]
    assert chooser.queue == []
