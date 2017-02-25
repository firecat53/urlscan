#   Copyright (C) 2006-2007 Daniel Burrows
#   Copyright (C) 2017 Scott Hansen
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


def process_urls(extractedurls, compact_mode, nobrowser, dedupe, shorten):
    """Process the 'extractedurls' and ready them for either the curses browser
    or non-interactive output

    Args: extractedurls
          compact_mode - No context displayed
          nobrowser - Just produce list of URLs for stdout
          dedupe - Remove duplicate URLs from list

    Returns: items - List of widgets for the ListBox
             urls - List of all URLs
             firstbutton - Number of first URL button
             if nobrowser, then _only_ return urls

    """
    cols, _ = urwid.raw_display.Screen().get_cols_rows()
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
        if dedupe is True:
            # If no unique URLs exist, then skip the group completely
            if not [chunk for chunks in group for chunk in chunks
                    if chunk.url is not None and chunk.url not in urls]:
                continue
        groupurls = []
        markup = []
        if compact_mode:
            lasturl = None
            for chunks in group:
                for chunk in chunks:
                    if chunk.url and chunk.url != lasturl \
                            and ((dedupe is True and chunk.url not in urls) or
                                 dedupe is False):
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
            if firstbutton == 0 and not compact_mode:
                firstbutton = len(items)
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

    if not items:
        items.append(urwid.Text("No URLs found"))
        firstbutton = 1
    if nobrowser is True:
        return urls
    else:
        return items, urls, firstbutton


class URLChooser:
    def __init__(self, extractedurls, compact_mode=False, dedupe=False,
                 shorten=False):
        self.shorten = shorten
        self.items, self.urls, firstbutton = process_urls(extractedurls,
                                                          compact_mode,
                                                          nobrowser=False,
                                                          dedupe=dedupe,
                                                          shorten=self.shorten)
        listbox = urwid.ListBox(self.items)
        listbox.set_focus(firstbutton)
        if len(self.urls) == 1:
            header = 'Found 1 url.'
        else:
            header = 'Found %d urls.' % len(self.urls)
        header = "{} :: {}".format(header, "q - Quit :: "
                                   "s - toggle selected URL shortener :: "
                                   "S - toggle all URL shorteners")
        headerwid = urwid.AttrMap(urwid.Text(header), 'header')
        self.top = urwid.Frame(listbox, headerwid)
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

    def main(self):
        loop = urwid.MainLoop(self.top, self.palette, screen=self.ui,
                              input_filter=self.handle_keys,
                              unhandled_input=self.unhandled)
        loop.run()

    def handle_keys(self, keys, raw):
        """Handle the enter or space key to trigger the 'loading' footer

        """
        for k in keys:
            if k == 'enter' or k == ' ':
                footerwid = urwid.AttrMap(urwid.Text("Loading URL..."),
                                          'footer')
                self.top.footer = footerwid
                load_thread = Thread(target=self._loading_thread, daemon=True)
                load_thread.start()
        return keys

    def unhandled(self, keys):
        """Add other keyboard actions (q, j, k) not handled by the ListBox
        widget.

        """
        size = self.ui.get_cols_rows()
        for k in keys:
            if k == 'q' or k == 'Q':
                raise urwid.ExitMainLoop()
            elif k == 'ctrl l':
                self.draw_screen(size)
            elif k == 'j':
                self.top.keypress(size, "down")
            elif k == 'k':
                self.top.keypress(size, "up")
            elif k == 's':
                # Toggle shortened URL for selected item
                fp = self.top.focus.focus_position
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
            else:
                self.top.keypress(size, k)

    def _loading_thread(self):
        """Simple thread to wait 5 seconds after launching a URL,
        clearing the screen and clearing the footer loading message.

        """
        sleep(5)
        footerwid = urwid.AttrMap(urwid.Text(""), "default")
        self.top.footer = footerwid
        size = self.ui.get_cols_rows()
        self.draw_screen(size)

    def draw_screen(self, size):
        self.ui.clear()
        canvas = self.top.render(size, focus=True)
        self.ui.draw_screen(size, canvas)
