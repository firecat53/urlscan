urlscan
=======
Daniel Burrows <dburrows@debian.org> (Original Author)
------------------------------------
Scott Hansen `<firecat4153 at moc.liamg reversed>` (Maintainer)
-----------------------------------------------

1. Purpose and Requirements

    Urlscan is  a small program that  is designed to  integrate with the
"mutt" mailreader to allow you to easily launch a Web browser for URLs
contained in  email messages.  It  is a replacement for  the "urlview"
program.

    Requires: Python 2.6 + and the python-urwid  library (python2-urwid for
Archlinux)

    If you are not using Archlinux, the shebangs will need to be adjusted, as
Arch uses `#!/usr/bin/env python2`

2. Features

    Urlscan parses an  email message passed on standard  input and scans
it for URLs.   It then displays the URLs and  their context within the
message, and allows you to choose one or more URLs to send to your Web
browser.

    Relative to urlview, urlscan has the following additional features:

    - Support for emails in quoted-printable and base64 encodings.  No
      more stripping out =40D from URLs by hand!

    - The context  of each  URL is provided  along with the  URL.  For
      HTML mails, a crude parser is used to render the HTML into text.

3. Setting up urlscan

    To  set up  urlscan, install  the "urlscan-git" package  (or use setup.py
to install the program).   Once urlscan is installed, add the following lines
to your .muttrc:

    `macro index,pager \cb "<pipe-message> urlscan<Enter>" "call urlscan to extract URLs out of a message"`

    `macro attach,compose \cb "<pipe-entry> urlscan<Enter>" "call urlscan to extract URLs out of a message"`

    Once  this  is done,  Control-b  while  reading  mail in  mutt  will
automatically invoke urlscan on the message.

    To choose  a particular  browser,  set the environment variable BROWSER; e.g.,

    `export BROWSER=/usr/bin/epiphany`

4. Known bugs and limitations

    - Because  the   Python  curses  module  does   not  support  wide
      characters  (see Debian bug  #336861), non-ASCII  characters can
      cause unpredictable  results in  urlscan.  This problem  will go
      away if Python and urwid are patched to support wide characters.

    - Running urlscan  sometimes "messes up"  the terminal background.
      This seems to  be an urwid bug, but I  haven't tracked down just
      what's going on.

    - Extraction of context from  HTML messages leaves something to be
      desired.   Probably  the  ideal  solution would  be  to  extract
      context on a word basis rather than on a paragraph basis.

    - The HTML message handling is a bit kludgy in general.

    - multipart/alternative  sections are  handled by  descending into
      all the sub-parts, rather than  just picking one, which may lead
      to URLs and context appearing twice.

    - Configurability is more than a little bit lacking.

5. [Archlinux Package](https://aur.archlinux.org/packages.php?ID=44853)
