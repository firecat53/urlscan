Urlscan
=======

Contributors
------------

Daniel Burrows <dburrows@debian.org> (Original Author)

Scott Hansen <firecat4153@gmail.com> (Maintainer)

Maxime Chatelle <xakz@rxsoft.eu> (Debian Maintainer)

Purpose and Requirements
------------------------

Urlscan is a small program that is designed to integrate with the "mutt" mailreader to allow you to easily launch a Web browser for URLs contained in email messages. It is a replacement for the "urlview" program.

Requires: Python 2.6+ (including Python 3.x) and the python-urwid library

Features
--------

Urlscan parses an email message or file and scans it for URLs and email addresses. It then displays the URLs and their context within the message, and allows you to choose one or more URLs to send to your Web browser. Alternatively, it send a list of all URLs to stdout.

Relative to urlview, urlscan has the following additional features:

- Support for emails in quoted-printable and base64 encodings. No more stripping out =40D from URLs by hand!

- The context of each URL is provided along with the URL. For HTML mails, a crude parser is used to render the HTML into text.

Installation and setup
----------------------

To install urlscan, install from your distribution repositories, from Pypi, install the `Archlinux Package`_ , or install from source using setup.py.

.. NOTE::

    To work with Python 3.x the minimum required version of urwid is 1.2.1. Python 2.x works fine with urwid >= 1.0.1

Once urlscan is installed, add the following lines to your .muttrc:

    macro index,pager \\cb "<pipe-message> urlscan<Enter>" "call urlscan to extract URLs out of a message"

    macro attach,compose \\cb "<pipe-entry> urlscan<Enter>" "call urlscan to extract URLs out of a message"

Once this is done, Control-b while reading mail in mutt will automatically invoke urlscan on the message.

To choose a particular browser, set the environment variable BROWSER:

    export BROWSER=/usr/bin/epiphany


Command Line usage
------------------

::

    urlscan [-n] <file>

Urlscan can extract URLs and email addresses from emails, or any text file. Calling without the '-n' flag will start the curses browser. Calling with '-n' will just output a list of URLs/email addressess to stdout. Files can also be piped to urlscan using normal shell pipe mechanisms: `cat <something> | urlscan` or `urlscan < <something>`

Known bugs and limitations
--------------------------

- Running urlscan sometimes "messes up" the terminal background. This seems to be an urwid bug, but I haven't tracked down just what's going on.

- Extraction of context from HTML messages leaves something to be desired. Probably the ideal solution would be to extract context on a word basis rather than on a paragraph basis.

- The HTML message handling is a bit kludgy in general.

- multipart/alternative sections are handled by descending into all the sub-parts, rather than just picking one, which may lead to URLs and context appearing twice.

- Configurability is more than a little bit lacking.

.. _Archlinux Package: https://aur.archlinux.org/packages/urlscan-git/
