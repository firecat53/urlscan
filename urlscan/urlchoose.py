#   Copyright (C) 2006-2007 Daniel Burrows
#   Copyright (C) 2018 Scott Hansen
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

"""An urwid listview-based widget that lets you choose a URL from a list of
URLs."""

import urwid
import urwid.curses_display
import urwid.raw_display
import webbrowser
from threading import Thread
from time import sleep


def mkbrowseto(url):
    """Create the urwid callback function to open the web browser.

    """
    def browse(*args):
        webbrowser.open(url)
    return browse


def shorten_url(url, cols, shorten):
    """Shorten long URLs to fit on one line.

    """
    cols = ((cols - 6) * .85)  # 6 cols for urlref and don't use while line
    if shorten is False or len(url) < cols:
        return url
    split = int(cols * .5)
    return url[:split] + "..." + url[-split:]


def process_urls(extractedurls, dedupe, shorten):
    """Process the 'extractedurls' and ready them for either the curses browser
    or non-interactive output

    Args: extractedurls
          dedupe - Remove duplicate URLs from list

    Returns: items - List of widgets for the ListBox
             urls - List of all URLs

    """
    cols, _ = urwid.raw_display.Screen().get_cols_rows()
    items = []
    urls = []
    first = True
    for group, usedfirst, usedlast in extractedurls:
        if first:
            first = False
        items.append(urwid.Divider(div_char='-', top=1, bottom=1))
        if dedupe is True:
            # If no unique URLs exist, then skip the group completely
            if not [chunk for chunks in group for chunk in chunks
                    if chunk.url is not None and chunk.url not in urls]:
                continue
        groupurls = []
        markup = []
        if not usedfirst:
            markup.append(('msgtext:ellipses', '...\n'))
        for chunks in group:
            i = 0
            while i < len(chunks):
                chunk = chunks[i]
                i += 1
                if chunk.url is None:
                    markup.append(chunk.markup)
                elif (dedupe is True and chunk.url not in urls) \
                        or dedupe is False:
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
            i += 1
            markup = [(6, urwid.Text([('urlref:number:braces', '['),
                                      ('urlref:number', repr(i)),
                                      ('urlref:number:braces', ']'),
                                      ' '])),
                      urwid.AttrMap(urwid.Button(shorten_url(url,
                                                             cols,
                                                             shorten),
                                                 mkbrowseto(url),
                                                 user_data=url),
                                    'urlref:url', 'url:sel')]
            items.append(urwid.Columns(markup))

    return items, urls


class URLChooser:
    def __init__(self, extractedurls, compact=False, dedupe=False, shorten=True):
        self.shorten = shorten
        self.compact = compact
        self.items, self.urls = process_urls(extractedurls,
                                             dedupe=dedupe,
                                             shorten=self.shorten)
        # Store 'compact' mode items
        self.items_com = [i for i in self.items if
                          isinstance(i, urwid.Columns) is True]
        if self.compact is True:
            self.items, self.items_com = self.items_com, self.items
        self.contents = urwid.SimpleFocusListWalker(self.items)
        listbox = urwid.ListBox(self.contents)
        if len(self.urls) == 1:
            header = 'Found 1 url.'
        else:
            header = 'Found %d urls.' % len(self.urls)
        header = "{} :: {}".format(header, "q - Quit :: "
                                   "c - context :: "
                                   "s - URL short :: "
                                   "S - all URL short :: "
                                   "<number> - jump to <number> :: ")
        headerwid = urwid.AttrMap(urwid.Text(header), 'header')
        self.top = urwid.Frame(listbox, headerwid)
        if self.urls:
            self.top.body.focus_position = \
                (2 if self.compact is False else 0)
        self.ui = urwid.curses_display.Screen()
        self.palette = [
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
            ('urlref:url', 'white', 'black', 'standout'),
            ('url:sel', 'white', 'dark blue', 'bold')
        ]
        self.number = ""

    def main(self):
        loop = urwid.MainLoop(self.top, self.palette, screen=self.ui,
                              input_filter=self.handle_keys,
                              unhandled_input=self.unhandled)
        loop.run()

    def handle_keys(self, keys, raw):
        """Handle the enter or space key to trigger the 'loading' footer

        """
        for k in keys:
            if (k == 'enter' or k == ' ') and self.urls:
                self._footer_start_thread("Loading URL...", 5)
        # filter backspace out before the widget, it has a weird interaction
        return [i for i in keys if i != 'backspace']

    def unhandled(self, keys):
        """Add other keyboard actions (q, j, k, s, S, c) not handled by the
        ListBox widget.

        """
        size = self.ui.get_cols_rows()
        for k in keys:
            if k == 'q' or k == 'Q':
                raise urwid.ExitMainLoop()
            elif not self.urls:
                continue  # No other actions are useful with no URLs
            elif k.isdigit():
                self.number += k
                try:
                    if self.compact is False:
                        self.top.body.focus_position = \
                            self.items.index(self.items_com[max(int(self.number) - 1, 0)])
                    else:
                        self.top.body.focus_position = \
                            self.items.index(self.items[max(int(self.number) - 1, 0)])
                except IndexError:
                    self.number = self.number[:-1]
                self.top.keypress(size, "")  # Trick urwid into redisplaying the cursor
                if self.number:
                    self._footer_start_thread("Selection: {}".format(self.number), 1)
            elif k == 'ctrl l':
                self.draw_screen(size)
            elif k == 'j':
                self.top.keypress(size, "down")
            elif k == 'k':
                self.top.keypress(size, "up")
            elif k == 's':
                # Toggle shortened URL for selected item
                fp = self.top.body.focus_position
                url_idx = len([i for i in self.items[:fp + 1]
                               if isinstance(i, urwid.Columns)]) - 1
                url = self.urls[url_idx]
                short = False if "..." in self.items[fp][1].label else True
                self.items[fp][1].set_label(shorten_url(url, size[0], short))
            elif k == 'S':
                # Toggle all shortened URLs
                self.shorten = False if self.shorten is True else True
                urls = iter(self.urls)
                columns_idx = 1
                for item in self.items:
                    # Each Column has (Text, Button). Update the Button label
                    if isinstance(item, urwid.Columns):
                        item[1].set_label(shorten_url(next(urls),
                                                      size[0],
                                                      self.shorten))
                        columns_idx += 1
            elif k == 'c':
                # Show/hide context
                fp = self.top.body.focus_position
                self.items, self.items_com = self.items_com, self.items
                self.top.body = urwid.ListBox(self.items)
                self.top.body.focus_position = self._cur_focus(fp)
                self.compact = False if self.compact is True else True
            else:
                self.top.keypress(size, k)

    def _footer_start_thread(self, text, time):
        """Display given text in the footer. Clears after <time> seconds

        """
        footerwid = urwid.AttrMap(urwid.Text(text), 'footer')
        self.top.footer = footerwid
        load_thread = Thread(target=self._loading_thread, args=(time,))
        load_thread.daemon = True
        load_thread.start()

    def _loading_thread(self, time):
        """Simple thread to wait <time> seconds after launching a URL or
        displaying a URL selection number, clearing the screen and clearing the
        footer loading message.

        """
        sleep(time)
        self.number = ""  # Clear URL selection number
        footerwid = urwid.AttrMap(urwid.Text(""), "default")
        self.top.footer = footerwid
        size = self.ui.get_cols_rows()
        self.draw_screen(size)

    def _cur_focus(self, fp=0):
        # Return correct focus when toggling 'show context'
        if self.compact is False:
            idx = len([i for i in self.items_com[:fp + 1]
                      if isinstance(i, urwid.Columns)]) - 1
        elif self.compact is True:
            idx = [i for i in enumerate(self.items)
                   if isinstance(i[1], urwid.Columns)][fp][0]
        return idx

    def draw_screen(self, size):
        self.ui.clear()
        canvas = self.top.render(size, focus=True)
        self.ui.draw_screen(size, canvas)
