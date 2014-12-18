#!/usr/bin/env python

from setuptools import setup

setup(name="urlscan",
      version="0.8.0",
      description="View/select the URLs in an email message or file",
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
