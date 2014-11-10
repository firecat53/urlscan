#   Copyright (C) 2006-2007 Daniel Burrows
#   Copyright (C) 2014 Scott Hansen
#
#   This program is free software; you can redistribute it and/or
#   modify it under the terms of the GNU General Public License as
#   published by the Free Software Foundation; either version 2 of the
#   License, or (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#   General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program; see the file COPYING.  If not, write to
#   the Free Software Foundation, Inc., 59 Temple Place - Suite 330,
#   Boston, MA 02111-1307, USA.

"""An urwid listview-based widget that lets you choose a URL from a list of
URLs."""

import urwid
import urwid.curses_display
from . import browser


def mkbrowseto(url):
    return lambda *args: browser.browseto(url)


# Based on urwid examples.
class URLChooser:
    def __init__(self, extractedurls, compact_mode=False):
        self.compact_mode = compact_mode
        self.items = []
        first = True
        firstbutton = 0
        self.urls = []
        for group, usedfirst, usedlast in extractedurls:
            if first:
                first = False
            elif not self.compact_mode:
                self.items.append(urwid.Divider(div_char='-', top=1, bottom=1))
            groupurls = []
            markup = []
            if self.compact_mode:
                lasturl = None
                for chunks in group:
                    for chunk in chunks:
                        if chunk.url and chunk.url != lasturl:
                            groupurls.append(chunk.url)
                            self.urls.append(chunk.url)
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
                            self.urls.append(chunk.url)
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
                                       ('urlref:number', repr(len(self.urls))),
                                       ('urlref:number:braces', ']')]
                    markup += '\n'
                if not usedlast:
                    markup += [('msgtext:ellipses', '...\n\n')]

                self.items.append(urwid.Text(markup))

            i = len(self.urls) - len(groupurls)
            for url in groupurls:
                if firstbutton == 0 and not self.compact_mode:
                    firstbutton = len(self.items)
                i += 1
                markup = [('urlref:number:braces', '['),
                          ('urlref:number', repr(i)),
                          ('urlref:number:braces', ']'),
                          ' ',
                          ('urlref:url', url)]
                self.items.append(urwid.Button(markup,
                                               mkbrowseto(url),
                                               user_data=url))

        if not self.items:
            self.items.append(urwid.Text("No URLs found"))
            firstbutton = 1
        self.listbox = urwid.ListBox(self.items)
        self.listbox.set_focus(firstbutton)
        if len(self.urls) == 1:
            header = 'Found 1 url.'
        else:
            header = 'Found %d urls.' % len(self.urls)
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
                    elif k == 'enter':
                        footer = "loading URL"
                        footerwid = urwid.AttrWrap(urwid.Text(footer),
                                                   'footer')
                        self.top.set_footer(footerwid)
                        self.top.keypress(size, k)
                    else:
                        self.top.keypress(size, k)
        except KeyboardInterrupt:
            return None

    def draw_screen(self, size):
        canvas = self.top.render(size, focus=True)
        self.ui.draw_screen(size, canvas)
