#!/usr/bin/env python3
""" A simple urlview replacement that handles things like quoted-printable
properly.

"""
#
#   Copyright (C) 2006-2007 Daniel Burrows
#   Copyright (C) 2021 Scott Hansen
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA

import argparse
import io
import os
import sys
from email import policy
from email.parser import BytesParser
from urlscan import urlchoose, urlscan


def parse_arguments():
    """Parse command line options.

    Returns: args

    """
    arg_parse = argparse.ArgumentParser(description="Parse and display URLs")
    arg_parse.add_argument('--genconf', '-g',
                           action='store_true', default=False,
                           help="Generate config file and exit.")
    arg_parse.add_argument('--compact', '-c',
                           action='store_true', default=False,
                           help="Don't display the context of each URL.")
    arg_parse.add_argument('--reverse', '-R', dest="reverse",
                           action='store_true', default=False,
                           help="Reverse order of displayed URLS/context")
    arg_parse.add_argument('--no-browser', '-n', dest="nobrowser",
                           action='store_true', default=False,
                           help="Pipe URLs to stdout")
    arg_parse.add_argument('--dedupe', '-d', dest="dedupe",
                           action='store_true', default=False,
                           help="Remove duplicate URLs from list")
    arg_parse.add_argument('--regex', '-E',
                           help="Alternate custom regex to be used for all "
                           "kinds of matching. "
                           "For example: --regex 'https?://.+\.\w+'")
    arg_parse.add_argument('--run', '-r',
                           help="Alternate command to run on selected URL "
                           "instead of opening URL in browser. Use {} to "
                           "represent the URL value in the expression. "
                           "For example: --run 'echo {} | xclip -i'")
    arg_parse.add_argument('--run-safe', '-f', dest="runsafe",
                           help="Alternate command to run on selected URL "
                           "instead of opening URL in browser. Use {} to "
                           "represent the URL value in the expression. Safest "
                           "run option but uses `shell=False` which does not "
                           "allow use of shell features like | or >. Can use "
                           "with --pipe.")
    arg_parse.add_argument('--pipe', '-p', dest='pipe',
                           action='store_true', default=False,
                           help="Pipe URL into the command specified by --run or --run-safe")
    arg_parse.add_argument('--nohelp', '-H', dest='nohelp',
                           action='store_true', default=False,
                           help='Hide help menu by default')
    arg_parse.add_argument('--single', '-s', dest='single',
                           action='store_true', default=False,
                           help='Quit urlscan after opening/copying a single link.')
    arg_parse.add_argument('--width', '-w', dest='width',
                           type=int, default=0,
                           help='Set width to display')
    arg_parse.add_argument('--whitespace-off', '-W', dest='whitespaceoff',
                           action='store_true', default=False,
                           help="Don't display empty lines and ellipses.")
    arg_parse.add_argument('--headers', dest='headers',
                           action='store_true', default=False,
                           help='Scan certain message headers for URLs.')
    arg_parse.add_argument('message', nargs='?', default=sys.stdin,
                           help="Filename of the message to parse")
    return arg_parse.parse_args()


def close_stdin():
    """This section closes out sys.stdin if necessary so as not to block curses
    keyboard inputs

    """
    if not os.isatty(0):
        try:
            fdesc = os.open('/dev/tty', os.O_RDONLY)
        except OSError:
            # This is most likely a non-interactive session, try to open
            # `stdin` directly
            fdesc = os.open('/dev/stdin', os.O_RDONLY)

        if fdesc < 0:
            sys.stderr.write('Unable to open an input tty.\n')
            sys.exit(-1)
        else:
            os.dup2(fdesc, 0)
            os.close(fdesc)


def process_input(fname):
    """Return the parsed text of stdin or the message. Accounts for possible
    file encoding differences.

        Args: fname - filename or sys.stdin
        Returns: mesg - EmailMessage object

    """
    if fname is sys.stdin:
        try:
            stdin_file = fname.buffer.read()
        except AttributeError:
            stdin_file = fname.read()
    else:
        stdin_file = None
    if stdin_file is not None:
        fobj = io.BytesIO(stdin_file)
    else:
        fobj = io.open(fname, mode='rb')
    f_keep = fobj
    mesg = BytesParser(policy=policy.default.clone(utf8=True)).parse(fobj)
    if 'From' not in mesg.keys() and 'Date' not in mesg.keys():
        # If it's not an email message, don't let the email parser
        # delete the first line. If it is, let the parser do its job so
        # we don't get mailto: links for all the To and From addresses
        fobj = _fix_first_line(f_keep)
        mesg = BytesParser(policy=policy.default.clone(utf8=True)).parse(fobj)
    try:
        fobj.close()
    except NameError:
        pass
    close_stdin()
    return mesg


def _fix_first_line(fline):
    """If the first line starts with http* or [ or other non-text characters,
    the URLs on that line will not be parsed by email.Parser. Add a blank line
    at the top of the file to ensure everything is read in a non-email file.

    """
    fline.seek(0)
    new = io.BytesIO()
    new.write(b"\n" + fline.read())
    fline.close()
    new.seek(0)
    return new


def main():
    """Entrypoint function for urlscan

    """
    args = parse_arguments()
    if args.genconf is True:
        urlchoose.URLChooser([], genconf=True)
        return
    msg = process_input(args.message)
    if args.nobrowser is False:
        tui = urlchoose.URLChooser(urlscan.msgurls(msg, regex=args.regex, headers=args.headers),
                                   compact=args.compact,
                                   reverse=args.reverse,
                                   nohelp=args.nohelp,
                                   dedupe=args.dedupe,
                                   run=args.run,
                                   runsafe=args.runsafe,
                                   single=args.single,
                                   width=args.width,
                                   whitespaceoff=args.whitespaceoff,
                                   pipe=args.pipe)
        tui.main()
    else:
        out = urlchoose.URLChooser(urlscan.msgurls(msg, regex=args.regex, headers=args.headers),
                                   dedupe=args.dedupe,
                                   reverse=args.reverse,
                                   shorten=False)
        if args.reverse is True:
            out.urls.reverse()
        print("\n".join(out.urls))


if __name__ == "__main__":
    main()
