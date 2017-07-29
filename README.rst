Instaloader
===========

Download pictures (or videos) along with their captions and other metadata
from Instagram.

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

(pass ``--upgrade`` to upgrade if Instaloader is already installed)

Instaloader requires
`requests <https://pypi.python.org/pypi/requests>`__, which
will be installed automatically, if it is not already installed.

How to automatically download pictures from Instagram
-----------------------------------------------------

To **download all pictures and videos of a profile**, as well as the
**profile picture**, do

::

    instaloader profile [profile ...]

where ``profile`` is the name of a profile you want to download. Instead
of only one profile, you may also specify a list of profiles.

To later **update your local copy** of that profiles, you may run

::

    instaloader --fast-update profile [profile ...]

When ``--fast-update`` is given, Instaloader stops when arriving at
the first already-downloaded picture.

Instaloader can also be used to **download private profiles**. To do so,
invoke it with

::

    instaloader --login=your_username profile [profile ...]

When invoked like this, it also **stores the session cookies** in a file
in your temporary directory, which will be reused later when ``--login`` is given. So
you can download private profiles **non-interactively** when you already
have a valid session cookie file.

Besides downloading private profiles, being logged in allows to
**download stories**:

::

    instaloader --login=your_username --stories profile [profile ...]

You may also download
**the most recent pictures by hashtag**:

::

    instaloader "#hashtag"

This downloads the requested posts into a directory named according to the specified
hashtag and the filenames correspond to the timestamp of the posts.
As with all download tasks, this behavior can easily be customized, for example
encode the poster's profile name in the filenames:

::

    instaloader --filename-pattern={date}_{profile} "#hashtag"

If you want to **download all followees of a given profile**, call

::

    instaloader --login=your_username @profile

To **download all the pictures from your feed which you have liked**, call

::

    instaloader --login=your_username :feed-liked

or to **download all pictures from your feed**:

::

    instaloader --login=your_username :feed-all

**Download all stories** from the profiles you follow:

::

    instaloader --login=your_username --filename-pattern={date}_{profile} :stories

Advanced Options
----------------

The following flags can be given to Instaloader to specify how profiles should
be downloaded.

To get a list of all flags, their abbreviations and their descriptions, you may
run ``instaloader --help``.

What to Download
^^^^^^^^^^^^^^^^

Specify a list of profiles or #hashtags. For each of these, Instaloader
creates a folder and downloads all posts along with the pictures's
captions and the current **profile picture**. If an already-downloaded profile
has been renamed, Instaloader automatically **finds it by its unique ID** and
renames the folder likewise.

Instead of a *profile* or a *#hashtag*, the special targets
``:feed-all`` (pictures from your feed),
``:feed-liked`` (pictures from your feed which you liked), and
``:stories`` (stories of your followees) can be specified.

--profile-pic-only         Only download profile picture.
--skip-videos              Do not download videos.
--geotags                  **Download geotags** when available. Geotags are stored as
                           a text file with the location's name and a Google Maps
                           link. This requires an additional request to the
                           Instagram server for each picture, which is why it is
                           disabled by default.
--comments                 Download and update comments for each post. This
                           requires an additional request to the Instagram server
                           for each post, which is why it is disabled by default.
--stories                  Also **download stories** of each profile that is
                           downloaded. Requires ``--login``.
--stories-only             Rather than downloading regular posts of each
                           specified profile, only download stories.
                           Requires ``--login``.

When to Stop Downloading
^^^^^^^^^^^^^^^^^^^^^^^^

If none of these options are given, Instaloader goes through all pictures
matching the specified targets.

--fast-update              For each target, stop when encountering the first
                           already-downloaded picture. This flag is recommended
                           when you use Instaloader to update your personal
                           Instagram archive.
--count COUNT              Do not attempt to download more than COUNT posts.
                           Applies only to ``#hashtag``, ``:feed-all`` and ``:feed-liked``.


Login (Download Private Profiles)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Instaloader can **login to Instagram**. This allows downloading private
profiles. To login, pass the ``--login`` option. Your session cookie (not your
password!) will be saved to a local file to be reused next time you want
Instaloader to login.

--login YOUR-USERNAME      Login name (profile name) for your Instagram account.
--sessionfile SESSIONFILE  Path for loading and storing session key file.
                           Defaults to a path
                           within your temporary directory, encoding your local
                           username and your Instagram profile name.
--password YOUR-PASSWORD   Password for your Instagram account. Without this
                           option, you'll be prompted for your password
                           interactively if there is not yet a valid session
                           file.

How to Download
^^^^^^^^^^^^^^^

--dirname-pattern DIRNAME_PATTERN
                           Name of directory where to store posts. ``{profile}``
                           is replaced by the profile name, ``{target}`` is replaced
                           by the target you specified, i.e. either ``:feed``,
                           ``#hashtag`` or the profile name. Defaults to ``{target}``.
--filename-pattern FILENAME_PATTERN
                           Prefix of filenames. Posts are stored in the
                           directory whose pattern is given with ``--dirname-pattern``.
                           ``{profile}`` is replaced by the profile name,
                           ``{target}`` is replaced by the target you specified, i.e.
                           either ``:feed``, ``#hashtag`` or the profile name. Also, the
                           fields ``{date}`` and ``{shortcode}`` can be specified.
                           Defaults to ``{date:%Y-%m-%d_%H-%M-%S}``.
--user-agent USER_AGENT    User Agent to use for HTTP requests. Per default,
                           Instaloader pretends being Chrome/51.
--no-sleep                 Do not sleep between requests to Instagram's servers.
                           This makes downloading faster, but may be suspicious.

Miscellaneous Options
^^^^^^^^^^^^^^^^^^^^^

--shorter-output           Do not display captions while downloading.
--quiet                    Disable user interaction, i.e. do not print messages
                           (except errors) and fail if login credentials are
                           needed but not given. This makes Instaloader
                           **suitable as a cron job**.

Usage as Python module
----------------------

You may also use parts of Instaloader as library to do other interesting
things.

For example, to get a list of all followees and a list of all followers of a profile, do

.. code:: python

    import instaloader

    # Get instance
    loader = instaloader.Instaloader()

    # Login
    loader.interactive_login(USERNAME)

    # Retrieve followees
    followees = loader.get_followees(PROFILE)
    print(PROFILE + " follows these profiles:")
    for f in followees:
        print("\t%s\t%s" % (f['username'], f['full_name']))

    # Retrieve followers
    followers = loader.get_followers(PROFILE)
    print("Followers of " + PROFILE + ":")
    for f in followers:
        print("\t%s\t%s" % (f['username'], f['full_name']))

Then, you may download all pictures of all followees with

.. code:: python

    for f in followees:
        try:
            loader.download(f['username'])
        except instaloader.NonfatalException:
            pass

You could also download your last 20 liked pics with

.. code:: python

    loader.download_feed_pics(max_count=20, fast_update=True,
                             filter_func=lambda node:
                                   not node["likes"]["viewer_has_liked"] if "likes" in node else not node["viewer_has_liked"])

To download the last 20 pictures with hashtag #cat, do

.. code:: python

    loader.download_hashtag('cat', max_count=20)

If logged in, Instaloader is also able to download user stories:

.. code:: python

    loader.download_stories()

Each Instagram profile has its own unique ID which stays unmodified even
if a user changes his/her username. To get said ID, given the profile's
name, you may call

.. code:: python

    loader.get_id_by_username(PROFILE_NAME)

``get_followees()`` also returns unique IDs for all loaded followees. To
get the current username of a profile, given this unique ID
``get_username_by_id()`` can be used. For example:

.. code:: python

    loader.get_username_by_id(followees[0]['id'])

Disclaimer
----------

This code is in no way affiliated with, authorized, maintained or endorsed by Instagram or any of its affiliates or
subsidiaries. This is an independent and unofficial project. Use at your own risk.