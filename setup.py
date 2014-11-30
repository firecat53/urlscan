#!/usr/bin/env python

from distutils.core import setup

setup(name="urlscan",
      version="0.7.2",
      description="View the URLs in an email message",
      author="Scott Hansen",
      author_email="firecat4153@gmail.com",
      packages=['urlscan'],
      scripts=['bin/urlscan'],
      package_data={'urlscan': ['README.rst']},
      data_files=[('share/doc/urlscan', ['README.rst', 'COPYING']),
                  ('share/man/man1', ['urlscan.1'])],
      license="GPLv2",
      install_requires=["urwid"]
      )
