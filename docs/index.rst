.. meta::
   :description:
      Command line tool to download pictures (and videos) from Instagram.
      Instaloader downloads public and private profiles, hashtags, user stories,
      feeds, comments, geotags, captions and other metadata of each post.

Instaloader
===========

.. highlight:: none

**Instaloader** is a tool to download pictures (or videos) along with
their captions and other metadata from Instagram.

With `Python <https://www.python.org/>`__ installed, do::

    $ pip3 install instaloader

    $ instaloader profile [profile ...]

**Instaloader**

- downloads **public and private profiles, hashtags, user stories and
  feeds**,

- downloads **comments, geotags and captions** of each post,

- automatically **detects profile name changes** and renames the target
  directory accordingly,

- allows **fine-grained customization** of filters and where to store
  downloaded media,

- is free `open source <https://github.com/Thammus/instaloader>`__
  software written in Python.

::

    instaloader [--comments] [--geotags] [--stories]
                [--login YOUR-USERNAME] [--fast-update]
                profile | "#hashtag"
                :stories | :feed | :saved


Table of Contents
-----------------

.. toctree::
   :maxdepth: 2

   installation
   basic-usage
   cli-options
   as-module
   contributing

Useful Links
------------

- `Git Repository (on GitHub) <https://github.com/Thammus/instaloader>`__
- `PyPI Project Page <https://pypi.python.org/pypi/instaloader>`__
- `Issue Tracker / Bug Tracker <https://github.com/Thammus/instaloader/issues>`__
- `Version History <https://github.com/Thammus/instaloader/releases>`__

.. include:: ../README.rst
   :start-after: disclaimer-start
   :end-before: disclaimer-end


..
   * :ref:`genindex`
   * :ref:`modindex`
   * :ref:`search`

