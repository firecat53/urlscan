# -*- coding: utf-8 -*-
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

"""Contains the backend logic that scans messages for URLs and context."""

from __future__ import unicode_literals
import re
import os
try:
    from HTMLParser import HTMLParser
except ImportError:
    from html.parser import HTMLParser


def get_charset(message, default="utf-8"):
    """Get the message charset"""
    if message.get_content_charset():
        return message.get_content_charset()
    if message.get_charset():
        return message.get_charset()
    return default


class Chunk:
    '''Represents a chunk of (marked-up) text that
    may or may not be linked to a URL.

    Attributes:
      markup - how this chunk will be rendered via urwid.
               This may be None if url is set, indicating
               that a URL footnote should be autogenerated.

      url    - the URL to which this text is linked, or None
               if no URL link is present.'''
    def __init__(self, markup, url):
        self.markup = markup
        self.url = url

    def __str__(self):
        return 'Chunk(markup = %s, url= %s)' % (repr(self.markup),
                                                repr(self.url))

    def __repr__(self):
        return self.__str__()


def isheadertag(t):
    return len(t) == 2 and t[0] == 'h' and t[1].isdigit()


class HTMLChunker(HTMLParser):
    """An HTMLParser that generates a sequence of lists of chunks.
    Each list represents a single paragraph."""

    def __init__(self):
        HTMLParser.__init__(self)

        # This attribute is the current output list.
        self.rval = []

        # If this attribute is True, the next chunk added will start a
        # new list.
        self.at_para_start = True
        self.trailing_space = False

        self.style_stack = [set()]
        self.anchor_stack = [None]
        self.list_stack = []
        # either 'ul' or 'ol' entries.

    # Styled text uses the named attribute
    # msgtext:style1style2... where the styles
    # are always sorted in alphabetic order.
    # (if the text is in an anchor, substitute
    # "msgtext:anchor" for "msgtext")
    tag_styles = {'b': 'bold', 'i': 'italic'}

    ul_tags = ['*', '+', '-']

    def cur_url(self):
        return self.anchor_stack[-1]

    def add_chunk(self, chunk):
        if self.at_para_start:
            self.rval.append([])
        elif self.trailing_space:
            self.rval[-1].append(Chunk(' ', self.cur_url()))

        self.rval[-1].append(chunk)
        self.at_para_start = False
        self.trailing_space = False

    def end_para(self):
        if self.at_para_start:
            self.rval.append([])
        else:
            self.at_para_start = True
        self.trailing_space = False
        if len(self.list_stack) > 0:
            self.add_chunk(Chunk(' ' * 3 * len(self.list_stack),
                                 self.cur_url()))

    def end_list_para(self):
        if self.at_para_start:
            self.rval.append([])
        if len(self.list_stack) > 0:
            tp = self.list_stack[-1][0]
            if tp == 'ul':
                depth = len([t for t in self.list_stack if t[0] == tp])
                ul_tags = HTMLChunker.ul_tags
                chunk = Chunk('%s  ' % (ul_tags[depth % len(ul_tags)]),
                              self.cur_url())
            else:
                counter = self.list_stack[-1][1]
                self.list_stack[-1] = (tp, counter + 1)
                chunk = Chunk("%2d." % counter, self.cur_url())
            self.add_chunk(chunk)
        else:
            self.end_para()

    def findattr(self, attrs, searchattr):
        for attr, val in attrs:
            if attr == searchattr:
                return val

        return None

    # TODO: should have better formatting.
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.anchor_stack.append(self.findattr(attrs, 'href'))
        elif tag == 'ul' or tag == 'ol':
            self.list_stack.append((tag, 1))
            self.end_para()
        elif tag in HTMLChunker.tag_styles:
            self.style_stack.append(self.style_stack[-1] |
                                    set([HTMLChunker.tag_styles[tag]]))
        elif isheadertag(tag):
            self.style_stack.append(self.style_stack[-1] | set(['bold']))
        elif tag == 'p' or tag == 'br':
            self.end_para()
        elif tag == 'img':
            # Since we expect HTML *email*, image links
            # should be external (naja?)
            alt = self.findattr(attrs, 'alt')
            if alt is None:
                alt = '[IMG]'
            src = self.findattr(attrs, 'src')
            if src is not None and src[:7] != 'http://':
                src = None

            if src is not None:
                self.anchor_stack.append(src)
                self.handle_data(alt)
                del self.anchor_stack[-1]
            else:
                self.handle_data(alt)
        elif tag == 'li':
            self.end_list_para()

    def handle_startendtag(self, tag, attrs):
        if tag in set(['p', 'br', 'li', 'img']):
            self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag == 'a':
            del self.anchor_stack[-1]
        elif tag in HTMLChunker.tag_styles:
            del self.style_stack[-1]
        elif tag == 'ul' or tag == 'ol':
            del self.list_stack[-1]
            self.end_para()
        elif isheadertag(tag):
            del self.style_stack[-1]
            self.end_para()

    def handle_data(self, data):
        future_trailing_space = False
        if len(data) > 0:
            if data[0].isspace():
                self.trailing_space = True
            if data[-1].isspace():
                future_trailing_space = True
        data = ' '.join(data.split())
        if self.anchor_stack[-1] is None:
            style = 'msgtext'
        else:
            style = 'anchor'
        if len(self.style_stack[-1]) > 0:
            stylelist = list(self.style_stack[-1])
            stylelist.sort()
            style = style + ':' + ''.join(stylelist)

        self.add_chunk(Chunk((style, data), self.cur_url()))
        self.trailing_space = future_trailing_space

    extrachars = {8212: "--",
                  8217: "'",
                  8220: "``",
                  8221: "''",
                  8230: "..."}

    def handle_charref(self, name):
        if name[0] == 'x':
            n = int(name[1:], 16)
        else:
            n = int(name)
        if n < 128:
            name = chr(n)
        elif n in HTMLChunker.extrachars:
            name = HTMLChunker.extrachars[n]
        else:
            name = '&#%s;' % name
        self.handle_data(name)

    entities = {'nbsp': ' ',
                'lt': '<',
                'gt': '>',
                'amp': '&',
                'ldquo': '``',
                'rdquo': "''",
                'apos': "'"}

    def handle_entityref(self, name):
        if name in HTMLChunker.entities:
            self.handle_data(HTMLChunker.entities[name])
        else:
            # If you see a reference, it needs to be
            # added above.
            self.handle_data('&%s;' % name)

urlinternalpattern = r'[{}()@\w/\-%?!&.=:;+,#~]'
urltrailingpattern = r'[{}()@\w/\-%&=+#]'
httpurlpattern = (r'(?:(https?|file|ftps?)://' + urlinternalpattern +
                  r'*' + urltrailingpattern + r')')
# Used to guess that blah.blah.blah.TLD is a URL.


def load_tlds():
    file = os.path.join(os.path.dirname(__file__),
                        'assets',
                        'tlds-alpha-by-domain.txt')
    with open(file) as f:
        return [elem for elem in f.read().lower().splitlines()[1:]
                if "--" not in elem]

tlds = ['biz', 'com', 'edu', 'info', 'org', 'de']
tlds = load_tlds()
guessedurlpattern = (r'(?:[\w\-%]+(?:\.[\w\-%]+)*\.(?:' +
                     '|'.join(tlds) + ')$)')
urlre = re.compile(r'(?:<(?:URL:)?)?(' + httpurlpattern + '|' +
                   guessedurlpattern +
                   '|(?P<email>(mailto:)?[\w\-.]*@[\w\-.]*[\w\-]))>?',
                   flags=re.U)

# Poor man's test cases.
assert(urlre.match('<URL:http://linuxtoday.com>'))
assert(urlre.match('http://linuxtoday.com'))
assert(re.compile(guessedurlpattern).match('example.biz'))
assert(urlre.match('example.biz'))
assert(urlre.match('linuxtoday.com'))
assert(urlre.match('master.wizard.edu'))
assert(urlre.match('blah.bar.info'))
assert(urlre.match('goodpr.org'))
assert(urlre.match('http://github.com/firecat53/ürlscan'))
assert(urlre.match('https://Schöne_Grüße.es/test'))
assert(urlre.match('http://www.pantherhouse.com/newshelton/my-wife-thinks-i’m-a-swan/'))
assert(not urlre.match('blah..org'))
assert(urlre.match('http://www.testurl.zw'))
assert(urlre.match('http://www.testurl.smile'))
assert(urlre.match('testurl.smile.smile'))
assert(urlre.match('testurl.biz.smile.zw'))
assert(not urlre.match('example..biz'))
assert(not urlre.match('blah.baz.obviouslynotarealdomain'))


def parse_text_urls(s):
    """Parse a block of text, splitting it into its url and non-url
    components."""

    rval = []

    loc = 0

    for match in urlre.finditer(s):
        if loc < match.start():
            rval.append(Chunk(s[loc:match.start()], None))
        # Turn email addresses into mailto: links
        email = match.group("email")
        if email and "mailto" not in email:
            m = "mailto:{}".format(email)
        else:
            m = match.group(1)
        rval.append(Chunk(None, m))
        loc = match.end()

    if loc < len(s):
        rval.append(Chunk(s[loc:], None))

    return rval


def extract_with_context(lst, pred, before_context, after_context):
    rval = []

    start = 0
    length = 0
    while start < len(lst):
        usedfirst = False
        usedlast = False
        # Extend to the next match.
        while start + length < len(lst) and length < before_context + 1 \
                and not pred(lst[start + length]):
            length += 1

        # Slide to the next match.
        while start + length < len(lst) and not pred(lst[start + length]):
            start += 1

        # If there was no next match, abort here (it's easier
        # to do this than to try to detect this case later).
        if start + length == len(lst):
            break

        # Now extend repeatedly until we can't find anything.
        while start + length < len(lst) and pred(lst[start + length]):
            extendlength = 1
            # Read in the 'after' context and see if it holds a URL.
            while extendlength < after_context + 1 and start + length + \
                    extendlength < len(lst) and \
                    not pred(lst[start + length + extendlength]):
                extendlength += 1
            length += extendlength
            if start + length < len(lst) and not pred(lst[start + length]):
                # Didn't find a matching line, so we either
                # hit the end or extended to after_context + 1..
                #
                # Now read in possible 'before' context
                # from the next URL; if we don't find one,
                # we discard the readahead.
                extendlength = 1
                while extendlength < before_context and start + length + \
                        extendlength < len(lst) and \
                        not pred(lst[start + length + extendlength]):
                    extendlength += 1
                if start + length + extendlength < len(lst) and \
                        pred(lst[start + length + extendlength]):
                    length += extendlength

        if length > 0 and start + length <= len(lst):
            if start == 0:
                usedfirst = True
            if start + length == len(lst):
                usedlast = True
            rval.append((lst[start:start + length], usedfirst, usedlast))

        start += length
        length = 0
    return rval


nlre = re.compile('\r\n|\n|\r')


def extracturls(s):
    """Given a text message, extract all the URLs found in the message, along
    with their surrounding context.  The output is a list of sequences of Chunk
    objects, corresponding to the contextual regions extracted from the string.

    """
    lines = nlre.split(s)

    # The number of lines of context above to provide.
    # above_context = 1
    # The number of lines of context below to provide.
    # below_context = 1

    # Plan here is to first transform lines into the form
    # [line_fragments] where each fragment is a chunk as
    # seen by parse_text_urls.  Note that this means that
    # lines with more than one entry or one entry that's
    # a URL are the only lines containing URLs.

    linechunks = [parse_text_urls(l) for l in lines]

    return extract_with_context(linechunks,
                                lambda chunk: len(chunk) > 1 or
                                (len(chunk) == 1 and chunk[0].url is not None),
                                1, 1)


def extracthtmlurls(s):
    c = HTMLChunker()
    c.feed(s)
    c.close()
    # above_context = 1
    # below_context = 1

    def somechunkisurl(chunks):
        for chunk in chunks:
            if chunk.url is not None:
                return True
        return False

    return extract_with_context(c.rval, somechunkisurl, 1, 1)


def msgurls(msg, urlidx=1):
    # Written as a generator so I can easily choose only
    # one subpart in the future (e.g., for
    # multipart/alternative).  Actually, I might even add
    # a browser for the message structure?
    enc = get_charset(msg)
    if msg.is_multipart():
        for part in msg.get_payload():
            for chunk in msgurls(part, urlidx):
                urlidx += 1
                yield chunk
    elif msg.get_content_type() == 'text/plain':
        msg = decode_bytes(msg.get_payload(decode=True), enc)
        for chunk in extracturls(msg):
            urlidx += 1
            yield chunk
    elif msg.get_content_type() == 'text/html':
        msg = decode_bytes(msg.get_payload(decode=True), enc)
        for chunk in extracthtmlurls(msg):
            urlidx += 1
            yield chunk


def decode_bytes(b, enc='utf-8'):
    """Given a string or bytes input, return a string.

        Args: b - bytes or string
              enc - encoding to use for decoding the byte string.

    """
    try:
        s = b.decode(enc)
    except UnicodeDecodeError as e:
        s = "Unable to decode message:\n{}\n{}".format(str(b), e)
    except (AttributeError, UnicodeEncodeError):
        # If b is already a string, just return it
        return b
    return s
