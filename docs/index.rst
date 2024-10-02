.. meta::
   :description:
      Free command line tool to download photos from Instagram.
      Scrapes public and private profiles, hashtags, stories, feeds,
      saved media, and their metadata, comments and captions.
      Written in Python.

.. title:: Instaloader — Download Instagram Photos and Metadata

Instaloader
===========

.. highlight:: none

**Instaloader** is a tool to download pictures (or videos) along with
their captions and other metadata from Instagram.

.. include:: ../README.rst
   :start-after: badges-start
   :end-before: badges-end

With `Python <https://www.python.org/>`__ installed, do::

    $ pip3 install instaloader

    $ instaloader profile [profile ...]

See :ref:`install` for more options on how to install Instaloader.

**Instaloader**

- downloads **public and private profiles, hashtags, user stories,
  feeds and saved media**,

- downloads **comments, geotags and captions** of each post,

- automatically **detects profile name changes** and renames the target
  directory accordingly,

- allows **fine-grained customization** of filters and where to store
  downloaded media,

- automatically **resumes previously-interrupted** download iterations,

- is free `open source <https://github.com/instaloader/instaloader>`__
  software written in Python.

::

    instaloader [--comments] [--geotags]
                [--stories] [--highlights] [--tagged] [--reels] [--igtv]
                [--login YOUR-USERNAME] [--fast-update]
                profile | "#hashtag" | %location_id |
                :stories | :feed | :saved

See :ref:`download-pictures-from-instagram` for a detailed introduction on how
to use Instaloader to download pictures from Instagram.

Instaloader Documentation
-------------------------

.. toctree::
   :maxdepth: 2

   installation
   basic-usage
   cli-options
   as-module
   codesnippets
   troubleshooting
   contributing

Useful Links
------------

- `Git Repository (on GitHub) <https://github.com/instaloader/instaloader>`__
- `PyPI Project Page <https://pypi.org/project/instaloader/>`__
- `Issue Tracker / Bug Tracker <https://github.com/instaloader/instaloader/issues>`__
- `Version History <https://github.com/instaloader/instaloader/releases>`__

Contributing
------------

As an open source project, Instaloader heavily depends on the contributions from
its community. See :ref:`contributing` for how you may help Instaloader to
become an even greater tool.

Supporters
----------

.. include:: sponsors.rst
   :start-after: donations-start
   :end-before: donations-end

Disclaimer
----------

.. include:: ../README.rst
   :start-after: disclaimer-start
   :end-before: disclaimer-end

..
   * :ref:`genindex`
   * :ref:`modindex`
   * :ref:`search`

