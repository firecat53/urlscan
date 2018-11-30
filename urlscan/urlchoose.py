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

import errno
import json
import os
from os.path import dirname, exists, expanduser
import re
from subprocess import Popen
from threading import Thread
from time import sleep
import webbrowser

import urwid
import urwid.curses_display
import urwid.raw_display

# Python 2 compatibility
try:
    FileNotFoundError
except NameError:
    FileNotFoundError = IOError

def shorten_url(url, cols, shorten):
    """Shorten long URLs to fit on one line.

    """
    cols = ((cols - 6) * .85)  # 6 cols for urlref and don't use while line
    if shorten is False or len(url) < cols:
        return url
    split = int(cols * .5)
    return url[:split] + "..." + url[-split:]


def grp_list(items):
    """Organize list of items [a,2,3,4,a,4,2,a,1, etc...] like:
        [[a,2,3,4], [a,4,2], [a,1]], where 'a' is a urwid.Divider

    """
    grp = []
    res = []
    for item in items:
        if isinstance(item, urwid.Divider):
            res.append(grp)
            grp = [items[0]]
        else:
            grp.append(item)
    res.append(grp)
    return res[1:]


def splittext(text, search, attr):
    """Split a text string by search string and add Urwid display attribute to
    the search term.

    Args: text - string
          search - search string
          attr - attribute string to add

    Returns: urwid markup list ["string", ("default", " mo"), "re string"]
             for search="mo", text="string more string" and attr="default"

    """
    if search:
        pat = re.compile("({})".format(re.escape(search)), re.IGNORECASE)
    else:
        return text
    final = pat.split(text)
    final = [(attr, i) if i.lower() == search.lower() else i for i in final]
    return final


class URLChooser:

    def __init__(self, extractedurls, compact=False, dedupe=False, shorten=True,
                 run=""):
        self.conf = expanduser("~/.config/urlscan/config.json")
        self.palettes = []
        try:
            with open(self.conf, 'r') as conf_file:
                data = json.load(conf_file)
                for pal in data.values():
                    self.palettes.append([tuple(i) for i in pal])
        except FileNotFoundError:
            pass
        # Default color palette
        self.palettes.append([('header', 'white', 'dark blue', 'standout'),
                              ('footer', 'white', 'dark red', 'standout'),
                              ('search', 'white', 'dark green', 'standout'),
                              ('msgtext', '', ''),
                              ('msgtext:ellipses', 'light gray', 'black'),
                              ('urlref:number:braces', 'light gray', 'black'),
                              ('urlref:number', 'yellow', 'black', 'standout'),
                              ('urlref:url', 'white', 'black', 'standout'),
                              ('url:sel', 'white', 'dark blue', 'bold')])
        # Default black & white palette
        self.palettes.append([('header', 'black', 'light gray', 'standout'),
                              ('footer', 'black', 'light gray', 'standout'),
                              ('search', 'black', 'light gray', 'standout'),
                              ('msgtext', '', ''),
                              ('msgtext:ellipses', 'white', 'black'),
                              ('urlref:number:braces', 'white', 'black'),
                              ('urlref:number', 'white', 'black', 'standout'),
                              ('urlref:url', 'white', 'black', 'standout'),
                              ('url:sel', 'black', 'light gray', 'bold')])

        self.shorten = shorten
        self.compact = compact
        self.run = run
        self.search = False
        self.search_string = ""
        self.no_matches = False
        self.enter = False
        self.items, self.urls = self.process_urls(extractedurls,
                                                  dedupe=dedupe,
                                                  shorten=self.shorten)
        # Store 'compact' mode items
        self.items_com = [i for i in self.items if
                          isinstance(i, urwid.Columns) is True]
        if self.compact is True:
            self.items, self.items_com = self.items_com, self.items
        self.urls_unesc = [i.replace('\\', '') for i in self.urls]
        self.unesc = False
        # Original version of all items
        self.items_orig = self.items
        # Store items grouped into sections
        self.items_org = grp_list(self.items)
        listbox = urwid.ListBox(self.items)
        header = (":: q - Quit :: "
                  "/ - search :: "
                  "c - context :: "
                  "s - URL short :: "
                  "S - all URL short :: "
                  "g/G - top/bottom :: "
                  "<num> - jump to <num> :: "
                  "p - cycle palettes :: "
                  "P - create config file ::"
                  "u - unescape URL ::")
        headerwid = urwid.AttrMap(urwid.Text(header), 'header')
        self.top = urwid.Frame(listbox, headerwid)
        if self.urls:
            self.top.body.focus_position = \
                (2 if self.compact is False else 0)
        self.tui = urwid.curses_display.Screen()
        self.palette_idx = 0
        self.number = ""

    def main(self):
        """Urwid main event loop

        """
        self.loop = urwid.MainLoop(self.top, self.palettes[0], screen=self.tui,
                                   handle_mouse=False, input_filter=self.handle_keys,
                                   unhandled_input=self.unhandled)
        self.loop.run()

    def handle_keys(self, keys, raw):
        """Handle widget default keys

            - 'Enter' or 'space' to load URL
            - 'Enter' to end search mode
            - add 'space' to search string in search mode
            - Workaround some small positioning bugs

        """
        for j, k in enumerate(keys):
            if self.search is True:
                text = "Search: {}".format(self.search_string)
                if k == 'enter':
                    # Catch 'enter' key to prevent opening URL in mkbrowseto
                    self.enter = True
                    if not self.items:
                        self.search = False
                        self.enter = False
                    if self.search_string:
                        footer = 'search'
                    else:
                        footer = 'default'
                        text = ""
                    footerwid = urwid.AttrMap(urwid.Text(text), footer)
                    self.top.footer = footerwid
                elif k == ' ':
                    self.search_string += " "
                    footerwid = urwid.AttrMap(urwid.Text(text), 'footer')
                    self.top.footer = footerwid
                elif k == 'backspace':
                    self.search_string = self.search_string[:-1]
                    self._search()
            elif k in ('enter', ' ') and self.urls and self.search is False:
                load_text = "Loading URL..." if not self.run else "Executing: {}".format(self.run)
                if os.environ.get('BROWSER') not in ['elinks', 'links', 'w3m', 'lynx']:
                    self._footer_start_thread(load_text, 5)
            if k == 'up':
                # Works around bug where the up arrow goes higher than the top list
                # item and unintentionally triggers context and palette switches.
                # Remaps 'up' to 'k'
                keys[j] = 'k'
            if k == 'home':
                # Remap 'home' to 'g'. Works around small bug where 'home' takes the cursor
                # above the top list item.
                keys[j] = 'g'
        # filter backspace out before the widget, it has a weird interaction
        return [i for i in keys if i != 'backspace']

    def unhandled(self, key):
        """Add other keyboard actions (q, j, k, s, S, c, g, G) not handled by
        the ListBox widget.

        """
        size = self.tui.get_cols_rows()
        if self.search is True:
            if self.enter is False and self.no_matches is False:
                if len(key) == 1 and key.isprintable():
                    self.search_string += key
                self._search()
            return
        if key in ('q', 'Q'):
            raise urwid.ExitMainLoop()
        elif not self.urls:
            pass  # No other actions are useful with no URLs
        elif key == '/':
            if self.urls:
                self.search = True
                if self.compact is True:
                    self.compact = False
                    self.items, self.items_com = self.items_com, self.items
            else:
                return
            self.no_matches = False
            self.search_string = ""
            # Reset the search highlighting
            self._search()
            footerwid = urwid.AttrMap(urwid.Text("Search: "), 'footer')
            self.top.footer = footerwid
            self.items = self.items_orig
            self.top.body = urwid.ListBox(self.items)
        elif key.isdigit():
            self.number += key
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
        elif key == 'ctrl l':
            self.draw_screen(size)
        elif key == 'j':
            self.top.keypress(size, "down")
        elif key == 'k':
            self.top.keypress(size, "up")
        elif key == 'g':
            # Goto top of the list
            self.top.body.focus_position = 2 if self.compact is False else 0
            self.top.keypress(size, "")  # Trick urwid into redisplaying the cursor
        elif key == 'G':
            # Goto bottom of the list
            self.top.body.focus_position = len(self.items) - 1
            self.top.keypress(size, "")  # Trick urwid into redisplaying the cursor
        elif key == 's':
            # Toggle shortened URL for selected item
            fpo = self.top.body.focus_position
            url_idx = len([i for i in self.items[:fpo + 1]
                           if isinstance(i, urwid.Columns)]) - 1
            if self.compact is False and fpo <= 1:
                return
            url = self.urls[url_idx]
            short = False if "..." in self.items[fpo][1].label else True
            self.items[fpo][1].set_label(shorten_url(url, size[0], short))
        elif key in ('S', 'u'):
            # Toggle all shortened or escaped URLs
            if key == 'S':
                self.shorten = False if self.shorten is True else True
            if key == 'u':
                self.unesc = False if self.unesc is True else True
                self.urls, self.urls_unesc = self.urls_unesc, self.urls
            urls = iter(self.urls)
            for item in self.items:
                # Each Column has (Text, Button). Update the Button label
                if isinstance(item, urwid.Columns):
                    item[1].set_label(shorten_url(next(urls),
                                                  size[0],
                                                  self.shorten))
        elif key == 'c':
            # Show/hide context
            if self.search_string:
                # Reset search when toggling compact mode
                footerwid = urwid.AttrMap(urwid.Text(""), 'default')
                self.top.footer = footerwid
                self.search_string = ""
                self.items = self.items_orig
            fpo = self.top.body.focus_position
            self.items, self.items_com = self.items_com, self.items
            self.top.body = urwid.ListBox(self.items)
            self.top.body.focus_position = self._cur_focus(fpo)
            self.compact = False if self.compact is True else True
        elif key == 'p':
            # Loop through available palettes
            self.palette_idx += 1
            try:
                self.loop.screen.register_palette(self.palettes[self.palette_idx])
            except IndexError:
                self.loop.screen.register_palette(self.palettes[0])
                self.palette_idx = 0
            self.loop.screen.clear()
        elif key == 'P':
            # Create ~/.config/urlscan/config.json if if doesn't exist
            if not exists(self.conf):
                try:
                    # Python 2/3 compatible recursive directory creation
                    os.makedirs(dirname(expanduser(self.conf)))
                except OSError as err:
                    if errno.EEXIST != err.errno:
                        raise
                names = ["default", "bw"]
                with open(expanduser(self.conf), 'w') as pals:
                    pals.writelines(json.dumps(dict(zip(names,
                                                        self.palettes)),
                                               indent=4))
                self._footer_start_thread("Created ~/.config/urlscan/config.json", 5)
            else:
                self._footer_start_thread("Config.json already exists", 5)

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
        text = "Search: {}".format(self.search_string)
        if self.search_string:
            footer = 'search'
        else:
            footer = 'default'
            text = ""
        footerwid = urwid.AttrMap(urwid.Text(text), footer)
        self.top.footer = footerwid
        size = self.tui.get_cols_rows()
        self.draw_screen(size)

    def _cur_focus(self, fpo=0):
        # Return correct focus when toggling 'show context'
        if self.compact is False:
            idx = len([i for i in self.items_com[:fpo + 1]
                       if isinstance(i, urwid.Columns)]) - 1
            idx = max(idx, 0)
        elif self.compact is True:
            idx = [i for i in enumerate(self.items)
                   if isinstance(i[1], urwid.Columns)][fpo][0]
        return idx

    def _search(self):
        """ Search - search URLs and text.

        """
        text = "Search: {}".format(self.search_string)
        footerwid = urwid.AttrMap(urwid.Text(text), 'footer')
        self.top.footer = footerwid
        search_items = []
        for grp in self.items_org:
            done = False
            for idx, item in enumerate(grp):
                if isinstance(item, urwid.Columns):
                    for col_idx, col in enumerate(item.contents):
                        if isinstance(col[0], urwid.decoration.AttrMap):
                            grp[idx][col_idx].set_label(splittext(col[0].base_widget.label,
                                                                  self.search_string,
                                                                  ''))
                            if self.search_string.lower() in col[0].base_widget.label.lower():
                                grp[idx][col_idx].set_label(splittext(col[0].base_widget.label,
                                                                      self.search_string,
                                                                      'search'))
                                done = True
                elif isinstance(item, urwid.Text):
                    grp[idx].set_text(splittext(item.text, self.search_string, ''))
                    if self.search_string.lower() in item.text.lower():
                        grp[idx].set_text(splittext(item.text, self.search_string, 'search'))
                        done = True
            if done is True:
                search_items.extend(grp)
        self.items = search_items
        self.top.body = urwid.ListBox(self.items)
        if self.items:
            self.top.body.focus_position = 2 if self.compact is False else 0
            # Trick urwid into redisplaying the cursor
            self.top.keypress(self.tui.get_cols_rows(), "")
            self.no_matches = False
        else:
            self.no_matches = True
            footerwid = urwid.AttrMap(urwid.Text(text + "  No Matches"), 'footer')
            self.top.footer = footerwid

    def draw_screen(self, size):
        """Render curses screen

        """
        self.tui.clear()
        canvas = self.top.render(size, focus=True)
        self.tui.draw_screen(size, canvas)

    def _get_search(self):
        return lambda: self.search, lambda: self.enter

    def mkbrowseto(self, url):
        """Create the urwid callback function to open the web browser or call
        another function with the URL.

        """
        # Try-except block to work around webbrowser module bug
        # https://bugs.python.org/issue31014
        try:
            browser = os.environ['BROWSER']
        except KeyError:
            pass
        else:
            del os.environ['BROWSER']
            webbrowser.register(browser, None, webbrowser.GenericBrowser(browser))
            try_idx = webbrowser._tryorder.index(browser)
            webbrowser._tryorder.insert(0, webbrowser._tryorder.pop(try_idx))

        def browse(*args):
            # double ()() to ensure self.search evaluated at runtime, not when
            # browse() is _created_. [0] is self.search, [1] is self.enter
            # self.enter prevents opening URL when in search mode
            if self._get_search()[0]() is True:
                if self._get_search()[1]() is True:
                    self.search = False
                    self.enter = False
            elif not self.run:
                webbrowser.open(url)
            else:
                Popen(self.run.format(url), shell=True).communicate()
            size = self.tui.get_cols_rows()
            self.draw_screen(size)
        return browse

    def process_urls(self, extractedurls, dedupe, shorten):
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
                        markup.append(('msgtext', chunk.markup))
                    else:
                        if (dedupe is True and chunk.url not in urls) \
                                or dedupe is False:
                            urls.append(chunk.url)
                            groupurls.append(chunk.url)
                        # Collect all immediately adjacent
                        # chunks with the same URL.
                        tmpmarkup = []
                        if chunk.markup:
                            tmpmarkup.append(('msgtext', chunk.markup))
                        while i < len(chunks) and \
                                chunks[i].url == chunk.url:
                            if chunks[i].markup:
                                tmpmarkup.append(chunks[i].markup)
                            i += 1
                        url_idx = urls.index(chunk.url) + 1 if dedupe is True else len(urls)
                        markup += [tmpmarkup or '<URL>',
                                   ('urlref:number:braces', ' ['),
                                   ('urlref:number', repr(url_idx)),
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
                                                     self.mkbrowseto(url),
                                                     user_data=url),
                                        'urlref:url', 'url:sel')]
                items.append(urwid.Columns(markup))

        return items, urls
