#!/usr/bin/env python3
"""urlscan setup.py"""

from setuptools import setup


def long_description():
    """Generate long description from README"""
    with open("README.md", encoding='utf-8') as readme:
        return readme.read()


setup(name="urlscan",
      version="0.9.8",
      description="View/select the URLs in an email message or file",
      long_description=long_description(),
      long_description_content_type="text/markdown",
      author="Scott Hansen",
      author_email="firecat4153@gmail.com",
      url="https://github.com/firecat53/urlscan",
      download_url="https://github.com/firecat53/urlscan/archive/0.9.8.zip",
      packages=['urlscan'],
      entry_points={
          'console_scripts': ['urlscan=urlscan.__main__:main']
      },
      package_data={'urlscan': ['assets/*']},
      data_files=[('share/doc/urlscan', ['README.md', 'COPYING']),
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
          'Programming Language :: Python :: 3.7',
          'Programming Language :: Python :: 3.8',
          'Programming Language :: Python :: 3.9',
          'Programming Language :: Python :: 3.10',
          'Topic :: Utilities'],
      keywords="urlscan, urlview, email, mutt, tmux"
      )
