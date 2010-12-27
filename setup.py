#!/usr/bin/env python2

from distutils.core import setup

setup(name="urlscan",
      version="0.5",
      description="View the URLs in an email message",
      author="Daniel Burrows",
      author_email="dburrows@debian.org",
      package_dir={'' : 'modules'},
      packages=['urlscan'],
      scripts=['urlscan'],
      )
