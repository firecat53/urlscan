#   Copyright (C) 2006-2007 Daniel Burrows
#   Copyright (C) 2016 Scott Hansen
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

"""An urwid listview-based widget that lets you choose a URL from a list of
URLs."""

import urwid
import urwid.curses_display
import webbrowser
from threading import Thread
from time import sleep


def mkbrowseto(url):
    """Create the urwid callback function to open the web browser.

    """
    def browse(*args):
        webbrowser.open(url)
    return browse


def process_urls(extractedurls, compact_mode=False, nobrowser=False):
    """Process the 'extractedurls' and ready them for either the curses browser
    or non-interactive output

    Args: extractedurls
          compact_mode - True/False (Default False)
          nobrowser - True/False (Default False)

    Returns: items
             urls
             firstbutton - Number of first URL button
             if nobrowser, then _only_ return urls

    """
    items = []
    urls = []
    first = True
    firstbutton = 0
    if nobrowser is True:
        compact_mode = True
    for group, usedfirst, usedlast in extractedurls:
        if first:
            first = False
        elif not compact_mode:
            items.append(urwid.Divider(div_char='-', top=1, bottom=1))
        groupurls = []
        markup = []
        if compact_mode:
            lasturl = None
            for chunks in group:
                for chunk in chunks:
                    if chunk.url and chunk.url != lasturl:
                        groupurls.append(chunk.url)
                        urls.append(chunk.url)
                        lasturl = chunk.url
        else:
            if not usedfirst:
                markup.append(('msgtext:ellipses', '...\n'))
            for chunks in group:
                i = 0
                while i < len(chunks):
                    chunk = chunks[i]
                    i += 1
                    if chunk.url is None:
                        markup.append(chunk.markup)
                    else:
                        urls.append(chunk.url)
                        groupurls.append(chunk.url)
                        # Collect all immediately adjacent
                        # chunks with the same URL.
                        tmpmarkup = []
                        if chunk.markup:
                            tmpmarkup.append(chunk.markup)
                        while i < len(chunks) and \
                                chunks[i].url == chunk.url:
                            if chunks[i].markup:
                                tmpmarkup.append(chunks[i].markup)
                            i += 1
                        markup += [tmpmarkup or '<URL>',
                                   ('urlref:number:braces', ' ['),
                                   ('urlref:number', repr(len(urls))),
                                   ('urlref:number:braces', ']')]
                markup += '\n'
            if not usedlast:
                markup += [('msgtext:ellipses', '...\n\n')]

            items.append(urwid.Text(markup))

        i = len(urls) - len(groupurls)
        for url in groupurls:
            if firstbutton == 0 and not compact_mode:
                firstbutton = len(items)
            i += 1
            markup = [('urlref:number:braces', '['),
                      ('urlref:number', repr(i)),
                      ('urlref:number:braces', ']'),
                      ' ',
                      ('urlref:url', url)]
            items.append(urwid.Button(markup,
                                      mkbrowseto(url),
                                      user_data=url))

    if not items:
        items.append(urwid.Text("No URLs found"))
        firstbutton = 1
    if nobrowser is True:
        return urls
    else:
        return items, urls, firstbutton


# Based on urwid examples.
class URLChooser:
    def __init__(self, extractedurls, compact_mode=False):
        items, urls, firstbutton = process_urls(extractedurls,
                                                compact_mode)
        self.listbox = urwid.ListBox(items)
        self.listbox.set_focus(firstbutton)
        if len(urls) == 1:
            header = 'Found 1 url.'
        else:
            header = 'Found %d urls.' % len(urls)
        headerwid = urwid.AttrWrap(urwid.Text(header), 'header')
        self.top = urwid.Frame(self.listbox, headerwid)

    def main(self):
        self.ui = urwid.curses_display.Screen()
        self.ui.register_palette([
            ('header', 'white', 'dark blue', 'standout'),
            ('footer', 'white', 'dark red', 'standout'),
            ('msgtext', 'light gray', 'black'),
            ('msgtext:bullet', 'white', 'black', 'standout'),
            ('msgtext:bold', 'white', 'black', 'standout'),
            ('msgtext:italic', 'dark cyan', 'black', 'standout'),
            ('msgtext:bolditalic', 'light cyan', 'black', 'standout'),
            ('anchor', 'yellow', 'black', 'standout'),
            ('anchor:bold', 'yellow', 'black', 'standout'),
            ('anchor:italic', 'yellow', 'black', 'standout'),
            ('anchor:bolditalic', 'yellow', 'black', 'standout'),
            ('msgtext:ellipses', 'light gray', 'black'),
            ('urlref:number:braces', 'light gray', 'black'),
            ('urlref:number', 'yellow', 'black', 'standout'),
            ('urlref:url', 'white', 'black', 'standout')
        ])
        return self.ui.run_wrapper(self.run)

    def run(self):
        size = self.ui.get_cols_rows()

        try:
            while True:
                self.ui.s.erase()
                self.draw_screen(size)
                keys = self.ui.get_input()
                for k in keys:
                    if k == 'window resize':
                        size = self.ui.get_cols_rows()
                    elif k == 'q':
                        return None
                    elif k == 'ctrl l':
                        self.ui.s.clear()
                    elif k == 'j':
                        self.top.keypress(size, "down")
                    elif k == 'k':
                        self.top.keypress(size, "up")
                    elif k == 'enter' or k == ' ':
                        footer = "loading URL"
                        footerwid = urwid.AttrWrap(urwid.Text(footer),
                                                   'footer')
                        self.top.set_footer(footerwid)
                        self.top.keypress(size, k)
                        load_thread = Thread(target=self._loading_thread)
                        load_thread.daemon = True
                        load_thread.start()
                        self.ui.s.clear()
                    else:
                        self.top.keypress(size, k)
        except KeyboardInterrupt:
            return None

    def _loading_thread(self):
        """Simple thread to wait 5 seconds after launching a URL,
        clearing the screen and clearing the footer loading message.

        """
        sleep(5)
        footerwid = urwid.AttrWrap(urwid.Text(""), "default")
        self.top.set_footer(footerwid)
        size = self.ui.get_cols_rows()
        self.draw_screen(size)

    def draw_screen(self, size):
        canvas = self.top.render(size, focus=True)
        self.ui.draw_screen(size, canvas)
