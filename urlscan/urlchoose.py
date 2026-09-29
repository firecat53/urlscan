#   Copyright (C) 2006-2007 Daniel Burrows
#   Copyright (C) 2023 Scott Hansen
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

import contextlib
import json
import os
from os.path import dirname, exists, expanduser
from sys import platform
import re
import shlex
import subprocess
import sys
from threading import Thread
import webbrowser

import urwid


if platform == 'darwin':
    COPY_COMMANDS = ('pbcopy',)
    COPY_COMMANDS_PRIMARY = ('pbcopy',)
    import selectors
    selectors.DefaultSelector = selectors.SelectSelector
elif 'WAYLAND_DISPLAY' in os.environ:
    COPY_COMMANDS = ('wl-copy',)
    COPY_COMMANDS_PRIMARY = ('wl-copy --primary',)
else:
    COPY_COMMANDS = ("xsel -ib", "xclip -i -selection clipboard")
    COPY_COMMANDS_PRIMARY = ("xsel -i", "xclip -i")

# Text-mode browsers take over the terminal and render to stdout, so they
# must be run in the foreground with the urwid screen suspended.
TERMINAL_BROWSERS = ('elinks', 'links', 'w3m', 'lynx')


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
        pat = re.compile(f"({re.escape(search)})", re.IGNORECASE)
    else:
        return text
    final = pat.split(text)
    final = [(attr, i) if i.lower() == search.lower() else i for i in final]
    return final


class URLButton(urwid.Button):
    """A Button that ignores every key, so that Enter and space reach
    URLChooser's keybindings like any other key.

    """
    def keypress(self, size, key):
        return key


class URLRow(urwid.Columns):
    """One URL in the list: its number and the (possibly shortened) URL.

        Args: url - the URL as extracted from the message
              number - the URL's number shown in the list
              label - the text to show for the URL

    """
    def __init__(self, url, number, label):
        self.url = url
        self.button = URLButton(label)
        super().__init__([(6, urwid.Text([('urlref:number:braces', '['),
                                          ('urlref:number', repr(number)),
                                          ('urlref:number:braces', ']'),
                                          ' '])),
                          urwid.AttrMap(self.button, 'urlref:url', 'url:sel')])


class URLChooser:

    def __init__(self, extractedurls, compact=False, reverse=False, nohelp=False, dedupe=False,
                 shorten=True, run="", runsafe="", single=False, pipe=False,
                 genconf=False, width=0, whitespaceoff=False, colors="true"):
        self.conf = expanduser("~/.config/urlscan/config.json")
        self.keys = {'enter': self._open_url,
                     ' ': self._open_url,
                     '/': self._search_key,
                     '0': self._digits,
                     '1': self._digits,
                     '2': self._digits,
                     '3': self._digits,
                     '4': self._digits,
                     '5': self._digits,
                     '6': self._digits,
                     '7': self._digits,
                     '8': self._digits,
                     '9': self._digits,
                     'a': self._add_url,
                     'C': self._clipboard,
                     'c': self._context,
                     'ctrl l': self._clear_screen,
                     'ctrl f': self._page_down,
                     'ctrl b': self._page_up,
                     'd': self._del_url,
                     'f1': self._help_menu,
                     'G': self._bottom,
                     'g': self._top,
                     'j': self._down,
                     'k': self._up,
                     'J': self._next,
                     'K': self._previous,
                     'P': self._clipboard_pri,
                     'l': self._link_handler,
                     'o': self._open_queue,
                     'O': self._open_queue_win,
                     'p': self._palette,
                     'Q': self._quit,
                     'q': self._quit,
                     'R': self._reverse,
                     'S': self._all_shorten,
                     's': self._shorten,
                     'u': self._all_escape
                     }
        # Set urwid color mode based on the colors parameter
        self.color = {
            "true": 2**24,
            "256": 256,
            "88": 88,
            "16": 16,
            "8": 8,
            "mono": 1
        }.get(colors, 16)
        self.palettes = {}
        # Default color palette
        default = [('header', 'white', 'dark blue', 'standout', '#ffffff', '#0000aa'),
                   ('footer', 'white', 'dark red', 'standout', '#ffffff', '#aa0000'),
                   ('search', 'white', 'dark green', 'standout', '#ffffff', '#00aa00'),
                   ('msgtext', '', '', '', '', ''),
                   ('msgtext:ellipses', 'light gray', 'black', '', '#aaaaaa', '#000000'),
                   ('urlref:number:braces', 'light gray', 'black', '', '#aaaaaa', '#000000'),
                   ('urlref:number', 'yellow', 'black', 'standout', '#ffff00', '#000000'),
                   ('urlref:url', 'white', 'black', 'standout', '#ffffff', '#000000'),
                   ('url:sel', 'white', 'dark blue', 'bold', '#ffffff', '#0000aa')]
        # Default black & white palette
        blw = [('header', 'black', 'light gray', 'standout', '#000000', '#aaaaaa'),
               ('footer', 'black', 'light gray', 'standout', '#000000', '#aaaaaa'),
               ('search', 'black', 'light gray', 'standout', '#000000', '#aaaaaa'),
               ('msgtext', '', '', '', '', ''),
               ('msgtext:ellipses', 'white', 'black', '', '#ffffff', '#000000'),
               ('urlref:number:braces', 'white', 'black', '', '#ffffff', '#000000'),
               ('urlref:number', 'white', 'black', 'standout', '#ffffff', '#000000'),
               ('urlref:url', 'white', 'black', 'standout', '#ffffff', '#000000'),
               ('url:sel', 'black', 'light gray', 'bold', '#000000', '#aaaaaa')]
        # Default catppuccin palette
        ctp = [("header", "white", "dark blue", "standout", "#CDD6F4", "#89B4FA"),
               ("footer", "white", "dark red", "standout", "#CDD6F4", "#F38BA8"),
               ("search", "white", "dark green", "standout", "#CDD6F4", "#A6E3A1"),
               ("msgtext", "", "", "", "#CDD6F4", "#1E1E2E"),
               ("msgtext:ellipses", "light gray", "black", "", "#B4BEFE", "#1E1E2E"),
               ("urlref:number:braces", "light gray", "black", "", "#B4BEFE", "#1E1E2E"),
               ("urlref:number", "yellow", "black", "standout", "#F9E2AF", "#1E1E2E"),
               ("urlref:url", "white", "black", "standout", "#CBA6F7", "#1E1E2E"),
               ("url:sel", "white", "dark blue", "bold", "#F5E0DC", "#313244")]

        if genconf is True:
            # Add default palettes for config generation
            self.palettes.update([("default", default), ("bw", blw), ("catppuccin", ctp)])
            self._config_create()

        # Flag to track if we found palettes in config.json
        config_has_palettes = False

        try:
            with open(self.conf, 'r', encoding=sys.getdefaultencoding()) as conf_file:
                data = json.load(conf_file)
                try:
                    if 'palettes' in data and data['palettes']:
                        # If config has palettes, use only those
                        config_has_palettes = True
                        for pal_name, pal in data['palettes'].items():
                            self.palettes.update([(pal_name, [tuple(i) for i in pal])])
                except KeyError:
                    pass
                try:
                    items = data['keys'].items()
                    for key, value in items:
                        if value:
                            self.keys[key] = getattr(self, f"_{value}")
                        else:
                            # An empty action unbinds the key
                            self.keys.pop(key, None)
                except KeyError:
                    pass
        except FileNotFoundError:
            pass

        # If no palettes were found in config, use the default hardcoded ones
        if not config_has_palettes:
            self.palettes.update([("default", default), ("bw", blw), ("catppuccin", ctp)])
        try:
            subprocess.run(['xdg-open'], check=False, stdout=subprocess.DEVNULL)
            self.xdg = True
        except OSError:
            self.xdg = False
        self.shorten = shorten
        self.compact = compact
        self.queue = []
        self.run = run
        self.runsafe = runsafe
        self.single = single
        self.pipe = pipe
        self.search = False
        self.search_string = ""
        self.no_matches = False
        self.term_width, _ = urwid.raw_display.Screen().get_cols_rows()
        self.width = min(self.term_width, width or self.term_width)
        self.whitespaceoff = whitespaceoff
        self.items, self.urls = self.process_urls(extractedurls,
                                                  dedupe=dedupe,
                                                  shorten=self.shorten)
        # Every URL row, whether or not the current view (search, compact)
        # shows it
        self.rows = [i for i in self.items if isinstance(i, URLRow)]
        # Original version of all items
        self.items_orig = self.items
        # Store items grouped into sections
        self.items_org = grp_list(self.items)
        # Store 'compact' mode items
        self.items_com = [i for i in self.items if
                          isinstance(i, URLRow)]
        if self.compact is True:
            self.items, self.items_com = self.items_com, self.items
        self.unesc = False
        listbox = urwid.ListBox(self.items)
        self.header = (":: F1 - help/keybindings :: "
                       "q - quit :: "
                       "/ - search :: "
                       "URL opening mode - {} :: "
                       "Queue - {}")
        self.link_open_modes = ["Web Browser", "Xdg-Open"] if self.xdg is True else ["Web Browser"]
        if self.runsafe:
            self.link_open_modes.insert(0, self.runsafe)
        elif self.run:
            self.link_open_modes.insert(0, self.run)
        self.nohelp = nohelp
        if nohelp is False:
            self.headerwid = urwid.AttrMap(urwid.Text(
                self.header.format(self.link_open_modes[0], len(self.queue))), 'header')
        else:
            self.headerwid = None
        self.top = urwid.Frame(listbox, self.headerwid)
        self.pad = self.term_width - self.width
        self.top = urwid.Padding(self.top, left=0, right=self.pad)
        if self.urls:
            self.top.base_widget.body.focus_position = \
                (2 if self.compact is False else 0)
        if reverse is True:
            self._reverse()
        self.tui = urwid.raw_display.Screen()
        self.palette_names = list(self.palettes.keys())
        self.palette_idx = 0
        self.number = ""
        self.help_menu = False

    def main(self):
        """Urwid main event loop

        """
        self.loop = urwid.MainLoop(self.top, self.palettes[self.palette_names[0]], screen=self.tui,
                                   handle_mouse=False, input_filter=self.handle_keys,
                                   unhandled_input=self.unhandled)
        self.loop.screen.set_terminal_properties(self.color)
        # Worker threads (URL opening) must not touch urwid directly. They
        # write a command to this pipe and _ui_pipe_callback runs it in the
        # main loop thread. The pipe is left open for the life of the process
        # so a thread still running after quit can't write to a reused fd.
        self.ui_pipe = self.loop.watch_pipe(self._ui_pipe_callback)
        self.loop.run()

    def _ui_pipe_callback(self, data):
        """Run commands sent from worker threads in the main loop thread.

            b"q" - quit
            b"r" - redraw the screen

        """
        if b"q" in data:
            self._quit()
        if b"r" in data:
            self.draw_screen()

    @property
    def size(self):
        _, rows = self.tui.get_cols_rows()
        return (self.width, rows)

    def handle_keys(self, keys, raw):
        """Filter keys before the ListBox sees them

            - Backspace in search mode
            - Any key closes the help menu
            - Workaround some small positioning bugs

        """
        for j, k in enumerate(keys):
            if self.search is True:
                if k == 'backspace':
                    self.search_string = self.search_string[:-1]
                    self._search()
            elif self.help_menu is True:
                self._help_menu()
                return []
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
        """Handle other keyboard actions not handled by the ListBox widget.

        """
        self.key = key
        if self.search is True:
            if key == 'enter':
                # Leave search mode, keeping the matches and their highlighting
                self.search = False
                self._search_footer()
            elif self.no_matches is False and len(key) == 1 and key.isprintable():
                self.search_string += key
                self._search()
            return
        if not self.urls and key not in "Qq":
            return  # No other actions are useful with no URLs
        if self.help_menu is False:
            try:
                self.keys[key]()
            except KeyError:
                pass

    def _quit(self):
        """q/Q"""
        raise urwid.ExitMainLoop()

    def _focused_row(self):
        """Return the URLRow with focus, or None if focus isn't on a URL."""
        if not self.items:
            return None
        row = self.top.base_widget.body.focus
        return row if isinstance(row, URLRow) else None

    def _url(self, row):
        """Return row's URL, unescaped if unescaping is toggled on (u)."""
        return row.url.replace('\\', '') if self.unesc is True else row.url

    def _set_label(self, row, short):
        """Show row's URL, shortened or not, keeping the queued marker."""
        star = "* " if row.button.label.startswith("* ") else ""
        row.button.set_label(star + shorten_url(self._url(row), self.size[0], short))

    def _open_url(self):
        """<Enter> or <space>"""
        row = self._focused_row()
        if row is None:
            return
        load_text = "Loading URL..." if self.link_open_modes[0] != (self.run or self.runsafe) \
            else f"Executing: {self.run or self.runsafe}"
        if os.environ.get('BROWSER') not in TERMINAL_BROWSERS:
            self._footer_display(load_text, 5)
        self.mkbrowseto(self._url(row))()

    def _background_queue(self, queue, mode):
        """Open URLs in background. Runs in a worker thread."""
        for url in queue:
            self.mkbrowseto(url, mode=mode, background=True)()
        os.write(self.ui_pipe, b"q" if self.single is True else b"r")

    def _queue(self, mode=2):
        """Open all URLs in queue

            Args: mode - 2 for new tab, 1 for new window

        """
        load_text = "Loading URLs in queue..." \
            if self.link_open_modes[0] != (self.run or self.runsafe) \
            else f"Executing: {self.run or self.runsafe}"
        if os.environ.get('BROWSER') in TERMINAL_BROWSERS:
            self._footer_display("Opening multiple links not support in text browsers", 5)
            return
        self._footer_display(load_text, 5)
        thr = Thread(target=self._background_queue, args=(self.queue, mode))
        thr.start()
        self.queue = []
        self.headerwid = urwid.AttrMap(urwid.Text(
            self.header.format(self.link_open_modes[0], len(self.queue))), 'header')
        self.top.base_widget.header = self.headerwid

    def _open_queue(self):
        """o (new tab)"""
        if self.queue:
            self._queue()

    def _open_queue_win(self):
        """O (new window)"""
        if self.queue:
            self._queue(1)

    def _add_url(self):
        """a"""
        row = self._focused_row()
        if row is None:
            return
        if self._url(row) not in self.queue:
            self.queue.append(self._url(row))
        self.headerwid = urwid.AttrMap(urwid.Text(
            self.header.format(self.link_open_modes[0], len(self.queue))), 'header')
        self.top.base_widget.header = self.headerwid
        label = row.button.label
        if not label.startswith("* "):
            row.button.set_label(f"* {label}")

    def _del_url(self):
        """d"""
        row = self._focused_row()
        if row is None:
            return
        try:
            self.queue.remove(self._url(row))
            self.headerwid = urwid.AttrMap(urwid.Text(
                self.header.format(self.link_open_modes[0], len(self.queue))), 'header')
            self.top.base_widget.header = self.headerwid
            label = row.button.label
            if label.startswith("* "):
                row.button.set_label(label[2:])
        except ValueError:
            pass

    def _help_menu(self):
        """F1"""
        if self.help_menu is False:
            self.focus_pos_saved = self.top.base_widget.body.focus_position
            help_men = "\n".join([f"{'space' if i == ' ' else i} - {j.__name__.strip('_')}"
                                  for i, j in self.keys.items() if j.__name__ !=
                                  '_digits'])
            help_men = "KEYBINDINGS\n" + help_men + "\n<0-9> - Jump to item"
            docs = ("OPTIONS\n"
                    "add_url       -- add URL to queue\n"
                    "all_escape    -- toggle unescape all URLs\n"
                    "all_shorten   -- toggle shorten all URLs\n"
                    "bottom        -- move cursor to last item\n"
                    "clear_screen  -- redraw screen\n"
                    "clipboard     -- copy highlighted URL to clipboard\n"
                    "                 using xsel/xclip\n"
                    "clipboard_pri -- copy highlighted URL to primary\n"
                    "                 selection using xsel/xclip\n"
                    "config_create -- create ~/.config/urlscan/config.json\n"
                    "context       -- show/hide context\n"
                    "del_url       -- delete URL from queue\n"
                    "down          -- cursor down\n"
                    "help_menu     -- show/hide help menu\n"
                    "link_handler  -- cycle through xdg-open, webbrowser \n"
                    "                 and user-defined function\n"
                    "next          -- jump to next URL\n"
                    "open_queue    -- open all URLs in queue\n"
                    "open_queue_win-- open all URLs in queue in new window\n"
                    "open_url      -- open selected URL\n"
                    "palette       -- cycle through palettes\n"
                    "previous      -- jump to previous URL\n"
                    "quit          -- quit\n"
                    "reverse       -- reverse order URLs/context\n"
                    "shorten       -- toggle shorten highlighted URL\n"
                    "single        -- quit urlscan after opening a\n"
                    "                 single link\n"
                    "top           -- move to first list item\n"
                    "up            -- cursor up\n")
            self.top.base_widget.body = \
                urwid.ListBox(urwid.SimpleListWalker([urwid.Columns([(24, urwid.Text(help_men)),
                                                                     urwid.Text(docs)])]))
        else:
            self.top.base_widget.body = urwid.ListBox(self.items)
            self.top.base_widget.body.focus_position = self.focus_pos_saved
        self.help_menu = not self.help_menu

    def _search_key(self):
        """ / """
        if self.urls:
            self.search = True
            if self.compact is True:
                self._context()
        else:
            return
        self.no_matches = False
        self.search_string = ""
        # Reset the search highlighting
        self._search()
        footerwid = urwid.AttrMap(urwid.Text("Search: "), 'footer')
        self.top.base_widget.footer = footerwid
        self.items = self.items_orig
        self.top.base_widget.body = urwid.ListBox(self.items)

    def _digits(self):
        """ 0-9 """
        self.number += self.key
        try:
            if self.compact is False:
                self.top.base_widget.body.focus_position = \
                    self.items.index(self.items_com[max(int(self.number) - 1, 0)])
            else:
                self.top.base_widget.body.focus_position = \
                    self.items.index(self.items[max(int(self.number) - 1, 0)])
        except IndexError:
            self.number = self.number[:-1]
        except ValueError:
            pass
        self.top.base_widget.keypress(self.size, "")  # Trick urwid into redisplaying the cursor
        if self.number:
            self._footer_display(f"Selection: {self.number}", 1)

    def _clear_screen(self):
        """ Ctrl-l """
        self.draw_screen()

    def _down(self):
        """ j """
        self.top.base_widget.keypress(self.size, "down")

    def _up(self):
        """ k """
        self.top.base_widget.keypress(self.size, "up")

    def _top(self):
        """ g """
        # Goto top of the list
        self.top.base_widget.body.focus_position = 2 if self.compact is False else 0
        self.top.base_widget.keypress(self.size, "")  # Trick urwid into redisplaying the cursor

    def _bottom(self):
        """ G """
        # Goto bottom of the list
        self.top.base_widget.body.focus_position = len(self.items) - 1
        self.top.base_widget.keypress(self.size, "")  # Trick urwid into redisplaying the cursor

    def _selectable_positions(self):
        return [i for i, item in enumerate(self.items) if item.selectable()]

    def _next(self):
        """ J """
        current_position = self.top.base_widget.body.focus_position
        if current_position >= self._selectable_positions()[-1]:
            # Do not jump if focus is on or after the last selectable position
            return
        # Jump to the first selectable position after the currently focused position
        target_position = min(p for p in self._selectable_positions() if p > current_position)
        self.top.base_widget.body.focus_position = target_position
        self.top.base_widget.keypress(self.size, "")  # Trick urwid into redisplaying the cursor

    def _page_up(self):
        """ Ctrl-b """
        self.top.base_widget.keypress(self.size, "page up")
        self.top.base_widget.keypress(self.size, "")  # Trick urwid into redisplaying the cursor

    def _page_down(self):
        """ Ctrl-f """
        self.top.base_widget.keypress(self.size, "page down")
        self.top.base_widget.keypress(self.size, "")  # Trick urwid into redisplaying the cursor

    def _previous(self):
        """ K """
        current_position = self.top.base_widget.body.focus_position
        if current_position <= self._selectable_positions()[0]:
            # Do not jump if focus is on or before the first selectable position
            return
        # Jump to the first selectable position before the currently focused position
        target_position = max(p for p in self._selectable_positions() if p < current_position)
        self.top.base_widget.body.focus_position = target_position
        self.top.base_widget.keypress(self.size, "")  # Trick urwid into redisplaying the cursor

    def _shorten(self):
        """ s """
        # Toggle shortened URL for selected item
        row = self._focused_row()
        if row is None:
            return
        self._set_label(row, "..." not in row.button.label)

    def _all_shorten(self):
        """ S """
        # Toggle all shortened URLs
        self.shorten = not self.shorten
        for row in self.rows:
            self._set_label(row, self.shorten)

    def _all_escape(self):
        """ u """
        # Toggle all escaped URLs
        self.unesc = not self.unesc
        for row in self.rows:
            self._set_label(row, self.shorten)

    def _reverse(self):
        """ R """
        # Reverse items
        fpo = self.top.base_widget.body.focus_position
        if self.compact is True:
            self.items.reverse()
        else:
            rev = []
            for item in self.items:
                if isinstance(item, urwid.Divider):
                    rev.insert(0, item)
                elif isinstance(item, urwid.Text):
                    rev.insert(1, item)
                else:
                    rev.insert(2, item)
            self.items = rev
        self.top.base_widget.body = urwid.ListBox(self.items)
        self.top.base_widget.body.focus_position = self._cur_focus(fpo)

    def _context(self):
        """ c """
        # Show/hide context
        if self.search_string:
            # Reset search when toggling compact mode
            footerwid = urwid.AttrMap(urwid.Text(""), 'default')
            self.top.base_widget.footer = footerwid
            self.search_string = ""
            self.items = self.items_orig
        fpo = self.top.base_widget.body.focus_position
        self.items, self.items_com = self.items_com, self.items
        self.top.base_widget.body = urwid.ListBox(self.items)
        self.top.base_widget.body.focus_position = self._cur_focus(fpo)
        self.compact = not self.compact

    def _clipboard(self, pri=False):
        """ C """
        # Copy highlighted url to clipboard
        row = self._focused_row()
        if row is None:
            return
        url = self._url(row)
        cmds = COPY_COMMANDS_PRIMARY if pri else COPY_COMMANDS
        for cmd in cmds:
            try:
                subprocess.run(shlex.split(cmd),
                               check=False,
                               input=url.encode(sys.getdefaultencoding()),
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
                self._footer_display("Copied url to "
                                     f"{'primary' if pri is True else 'clipboard'} selection", 5)
            except OSError:
                continue
            if self.single is True:
                self._quit()
            break

    def _clipboard_pri(self):
        """ P """
        # Copy highlighted url to primary selection
        self._clipboard(pri=True)

    def _palette(self):
        """ p """
        # Loop through available palettes
        self.palette_idx += 1
        try:
            self.loop.screen.register_palette(self.palettes[self.palette_names[self.palette_idx]])
        except IndexError:
            self.loop.screen.register_palette(self.palettes[self.palette_names[0]])
            self.palette_idx = 0
        self.loop.screen.clear()

    def _config_create(self):
        """ --genconf """
        # Create ~/.config/urlscan/config.json if if doesn't exist
        if not exists(self.conf):
            os.makedirs(dirname(expanduser(self.conf)), exist_ok=True)
            keys = dict(zip(self.keys.keys(),
                            [i.__name__.strip('_') for i in self.keys.values()]))
            with open(expanduser(self.conf), 'w', encoding=sys.getdefaultencoding()) as pals:
                pals.writelines(json.dumps({"palettes": self.palettes, "keys": keys},
                                           indent=4))
            print("Created ~/.config/urlscan/config.json")
        else:
            print("~/.config/urlscan/config.json already exists")

    def _footer_display(self, text, time):
        """Display given text in the footer. Clears after <time> seconds

        """
        footerwid = urwid.AttrMap(urwid.Text(text), 'footer')
        self.top.base_widget.footer = footerwid
        self.loop.set_alarm_in(time, self._footer_callback)

    def _footer_callback(self, _loop, _data):
        """Callback for loop set_alarm_in after launching a URL or displaying a
        URL selection number, clearing the screen and clearing the footer
        loading message.

        """
        self.number = ""  # Clear URL selection number
        self._search_footer()
        self.draw_screen()

    def _search_footer(self):
        """Show the search string in the footer, or clear it if there is none."""
        if self.search_string:
            footerwid = urwid.AttrMap(urwid.Text(f"Search: {self.search_string}"), 'search')
        else:
            footerwid = urwid.AttrMap(urwid.Text(""), 'default')
        self.top.base_widget.footer = footerwid

    def _cur_focus(self, fpo=0):
        # Return correct focus when toggling 'show context'
        if self.compact is False:
            idx = len([i for i in self.items_com[:fpo + 1]
                       if isinstance(i, URLRow)]) - 1
            idx = max(idx, 0)
        elif self.compact is True:
            idx = [i for i in enumerate(self.items)
                   if isinstance(i[1], URLRow)][fpo][0]
        return idx

    def _search(self):
        """ Search - search URLs and text.

        """
        text = f"Search: {self.search_string}"
        footerwid = urwid.AttrMap(urwid.Text(text), 'footer')
        self.top.base_widget.footer = footerwid
        search_items = []
        for grp in self.items_org:
            done = False
            for idx, item in enumerate(grp):
                if isinstance(item, URLRow):
                    for col_idx, col in enumerate(item.contents):
                        if isinstance(col[0], urwid.AttrMap):
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
        self.top.base_widget.body = urwid.ListBox(self.items)
        if self.items:
            self.top.base_widget.body.focus_position = 2 if self.compact is False else 0
            # Trick urwid into redisplaying the cursor
            self.top.base_widget.keypress(self.size, "")
            self.no_matches = False
        else:
            self.no_matches = True
            footerwid = urwid.AttrMap(urwid.Text(text + "  No Matches"), 'footer')
            self.top.base_widget.footer = footerwid

    def draw_screen(self):
        """Render curses screen

        """
        self.tui.clear()
        canvas = self.top.base_widget.render(self.size, focus=True)
        self.tui.draw_screen(self.size, canvas)

    def _link_handler(self):
        """Function to cycle through opening links via webbrowser module,
        xdg-open or custom expression passed with --run-safe or --run.

        """
        mode = self.link_open_modes.pop()
        self.link_open_modes.insert(0, mode)
        if self.nohelp is False:
            self.headerwid = urwid.AttrMap(urwid.Text(
                self.header.format(self.link_open_modes[0], len(self.queue))), 'header')
            self.top.base_widget.header = self.headerwid

    def mkbrowseto(self, url, mode=0, background=False):
        """Create a function to open the web browser or call another function
        with the URL.

        Args: background (default False)
                If False, runs browser in a thread so it doesn't block the
                urwid event loop.

        """
        def browse():
            if self.link_open_modes[0] == "Web Browser" \
                    and os.environ.get('BROWSER') in TERMINAL_BROWSERS:
                # Text-mode browsers need control of the real terminal and
                # their own stdout, so suspend the urwid screen and run them
                # in the foreground.
                self.loop.stop()
                try:
                    subprocess.run([os.environ['BROWSER'], url], check=False)
                finally:
                    self.loop.start()
                    self.draw_screen()
                if self.single is True:
                    self._quit()
                return
            with redirect_output():
                if self.link_open_modes[0] == "Web Browser":
                    webbrowser.open(url, new=mode)
                elif self.link_open_modes[0] == "Xdg-Open":
                    subprocess.run(shlex.split(f'xdg-open "{url}"'), check=False)
                elif self.link_open_modes[0] == self.runsafe:
                    if self.pipe:
                        subprocess.run(shlex.split(self.runsafe),
                                       check=False,
                                       input=url.encode(sys.getdefaultencoding()))
                    else:
                        cmd = [i.format(url) for i in shlex.split(self.runsafe)]
                        subprocess.run(cmd, check=False)
                elif self.link_open_modes[0] == self.run and self.pipe:
                    subprocess.run(shlex.split(self.run),
                                   check=False,
                                   input=url.encode(sys.getdefaultencoding()))
                else:
                    subprocess.run(self.run.format(url), check=False, shell=True)

            # This runs in a worker thread, so ask the main loop to quit.
            # When opening the queue (background), _background_queue quits
            # after the whole queue is opened instead.
            if self.single is True and background is False:
                os.write(self.ui_pipe, b"q")

        if background or os.environ.get('BROWSER') in TERMINAL_BROWSERS:
            return browse

        def browse_async():
            # daemon=True so quitting urlscan doesn't wait for a still-open
            # browser to close.
            Thread(target=browse, daemon=True).start()
        return browse_async

    def process_urls(self, extractedurls, dedupe, shorten):
        """Process the 'extractedurls' and ready them for either the curses browser
        or non-interactive output

        Args: extractedurls
              dedupe - Remove duplicate URLs from list

        Returns: items - List of widgets for the ListBox
                 urls - List of all URLs

        """
        items = []
        urls = []
        for group, usedfirst, usedlast in extractedurls:
            items.append(urwid.Divider(div_char='-', top=1, bottom=1))
            if dedupe is True:
                # If no unique URLs exist, then skip the group completely
                if not [chunk for chunks in group for chunk in chunks
                        if chunk.url is not None and chunk.url not in urls]:
                    continue
            groupurls = []
            markup = []
            if not usedfirst and not self.whitespaceoff:
                markup.append(('msgtext:ellipses', '...\n'))
            for chunks in group:
                i = 0
                while i < len(chunks):
                    chunk = chunks[i]
                    i += 1
                    if chunk.url is None:
                        markup.append(('msgtext', chunk.markup))
                    else:
                        chunk.url = chunk.url.strip()
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
                                (chunks[i].url if chunks[i].url is None
                                    else chunks[i].url.strip()) == chunk.url:
                            if chunks[i].markup:
                                tmpmarkup.append(chunks[i].markup)
                            i += 1
                        url_idx = urls.index(chunk.url) + 1 if dedupe is True else len(urls)
                        markup += [tmpmarkup or '<URL>',
                                   ('urlref:number:braces', ' ['),
                                   ('urlref:number', repr(url_idx)),
                                   ('urlref:number:braces', ']')]
                if not self.whitespaceoff:
                    markup += '\n'
            if not usedlast and not self.whitespaceoff:
                markup += [('msgtext:ellipses', '...\n\n')]
            items.append(urwid.Text(markup))

            i = len(urls) - len(groupurls)
            for url in groupurls:
                i += 1
                items.append(URLRow(url, i, shorten_url(url, self.width, shorten)))

        return items, urls


@contextlib.contextmanager
def redirect_output():
    """
    A context manager to temporarily redirect stderr and stdout to devnull

    Usage:
        with redirect_output():
            webbrowser.open('https://google.com')

    """
    try:
        err = os.dup(sys.stderr.fileno())
        out = os.dup(sys.stdout.fileno())
        dest_file = open(os.devnull, 'w')
        os.dup2(dest_file.fileno(), sys.stderr.fileno())
        os.dup2(dest_file.fileno(), sys.stdout.fileno())
        yield
    finally:
        if err is not None:
            os.dup2(err, sys.stderr.fileno())
        if out is not None:
            os.dup2(out, sys.stdout.fileno())
        if dest_file is not None:
            dest_file.close()
