#!/usr/bin/env python

from distutils.core import setup

setup(name="urlscan",
      version="0.7.0",
      description="View the URLs in an email message",
      author="Daniel Burrows",
      author_email="dburrows@debian.org",
      packages=['urlscan'],
      scripts=['bin/urlscan'],
      package_data={'urlscan': ['README.md']},
      data_files=[('share/doc/urlscan', ['README.md', 'COPYING']),
                  ('share/man/man1', ['urlscan.1'])],
      license="GPLv2",
      install_requires=["urwid"]
      )
