#!/usr/bin/env python3

from setuptools import setup

setup(name="urlscan",
      version="0.9.6",
      description="View/select the URLs in an email message or file",
      author="Scott Hansen",
      author_email="firecat4153@gmail.com",
      url="https://github.com/firecat53/urlscan",
      download_url="https://github.com/firecat53/urlscan/archive/0.9.6.zip",
      packages=['urlscan'],
      scripts=['bin/urlscan'],
      package_data={'urlscan': ['assets/*']},
      data_files=[('share/doc/urlscan', ['README.rst', 'COPYING']),
                  ('share/man/man1', ['urlscan.1'])],
      license="GPLv2",
      install_requires=["urwid>=1.2.1"],
      classifiers=[
          'Development Status :: 4 - Beta',
          'Environment :: Console',
          'Environment :: Console :: Curses',
          'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
          'Operating System :: OS Independent',
          'Programming Language :: Python',
          'Programming Language :: Python :: 3.6',
          'Programming Language :: Python :: 3.7',
          'Programming Language :: Python :: 3.8',
          'Programming Language :: Python :: 3.9',
          'Topic :: Utilities'],
      keywords=("urlscan urlview email mutt tmux"),
      )
