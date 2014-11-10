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

"""Contains logic to invoke the default system browser."""

import webbrowser


def browseto(url):
    if not url.startswith('http'):
        url = "http://{}".format(url)
    webbrowser.open(url)
