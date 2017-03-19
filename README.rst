Instaloader
===========


Installation
------------

Instaloader is written in Python, thus ensure having
`Python <https://www.python.org/>`__ (at least version 3.5) installed.

If you intend to use this tool under Windows, it is recommended
to install
`win-unicode-console <https://pypi.python.org/pypi/win_unicode_console>`__.

If you have `pip <https://pypi.python.org/pypi/pip>`__ installed, you
may install Instaloader using

::

    pip3 install instaloader

Alternatively, to get the most current version of Instaloader from our
`Git repository <https://github.com/Thammus/instaloader>`__:

::

    pip3 install git+https://github.com/Thammus/instaloader

Instaloader requires
`requests <https://pypi.python.org/pypi/requests>`__, which
will be installed automatically, if it is not already installed.

How to automatically download pictures from Instagram
-----------------------------------------------------

To download a set of profiles, do

::

    instaloader profile [profile ...]

where ``profile`` is the name of a profile you want to download. Instead
of only one profile, you may also specify a list of profiles.

To later update your local copy of that profile, you may run

::

    instaloader --fast-update profile [profile ...]

When ``--fast-update`` is given, Instaloader terminates when arriving at
the first already-downloaded picture.

Instaloader can also be used to **download private profiles**. To do so,
invoke it with

::

    instaloader --login=your_username profile [profile ...]

When invoked like this, it also **stores the session cookies** in a file
in ``/tmp``, which will be reused later when ``--login`` is given. So
you can download private profiles **non-interactively** when you already
have a valid session cookie file.

If you want to **download all followees of a given profile**, call

::

    instaloader --login=your_username @profile

To **download all the pictures from your feed which you have liked**, call

::

    instaloader --login=your_username :feed-liked

The ``--quiet`` option makes it also **suitable as a cron job**.

To get a list of other helpful flags, run ``instaloader --help``.

Usage as library
----------------

You may also use parts of Instaloader as library to do other interesting
things.

For example, to get a list of all followers of a profile as well as
their follower count, do

.. code:: python

    import instaloader

    # login
    session = instaloader.get_logged_in_session(USERNAME)

    # get followees
    followees = instaloader.get_followees(PROFILE, session)
    for f in followees:
        print("%i\t%s\t%s" % (f['follower_count'], f['username'], f['full_name']))

Then, you may download all pictures of all followees with

.. code:: python

    for f in followees:
        try:
            instaloader.download(f['username'], session)
        except instaloader.NonfatalException:
            pass

You could also download your last 20 liked pics with

.. code:: python

    instaloader.download_feed_pics(session, max_count=20, fast_update=True,
                                   filter_func=lambda node: not node["likes"]["viewer_has_liked"])

Each Instagram profile has its own unique ID which stays unmodified even
if a user changes his/her username. To get said ID, given the profile's
name, you may call

.. code:: python

    instaloader.get_id_by_username(PROFILE_NAME)

``get_followees()`` also returns unique IDs for all loaded followees. To
get the current username of a profile, given this unique ID
``get_username_by_id()`` can be used. For example:

.. code:: python

    instaloader.get_username_by_id(session, followees[0]['id'])
