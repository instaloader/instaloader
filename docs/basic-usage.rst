.. meta::
   :description:
      How to download pictures from Instagram. Description of basic
      usage of Instaloader, free tool to download photos from public
      and private profiles, hashtags, stories, feeds, saved media, and
      their metadata, comments and captions.

.. _download-pictures-from-instagram:

Download Pictures from Instagram
---------------------------------

.. highlight:: none

Here we describe how to use Instaloader to download pictures from Instagram. If
you do not have Instaloader installed yet, see :ref:`install`.

.. NOTE that Section "Basic Usage" is duplicated in README.rst.

Basic Usage
^^^^^^^^^^^

To **download all pictures and videos of a profile**, as well as the
**profile picture**, do

::

    instaloader profile [profile ...]

where ``profile`` is the name of a profile you want to download. Instead
of only one profile, you may also specify a list of profiles.

To later **update your local copy** of that profiles, you may run

::

    instaloader --fast-update profile [profile ...]

If :option:`--fast-update` is given, Instaloader stops when arriving at the
first already-downloaded picture.

When updating profiles, Instaloader
automatically **detects profile name changes** and renames the target directory
accordingly.

Instaloader can also be used to **download private profiles**. To do so,
invoke it with

::

    instaloader --login=your_username profile [profile ...]

When logging in, Instaloader **stores the session cookies** in a file in your
home directory, which will be reused later the next time :option:`--login`
is given.  So you can download private profiles **non-interactively** when you
already have a valid session cookie file.

.. _what-to-download:

What to Download
^^^^^^^^^^^^^^^^

.. targets-start

Instaloader supports the following targets:

- ``profile``
   Public profile, or private profile with :option:`--login`.

   If an already-downloaded profile has been renamed, Instaloader automatically
   finds it by its unique ID and renames the folder accordingly.

   Besides the profile's posts, its current profile picture is downloaded. For
   each profile you download,

   - :option:`--stories`
      instructs Instaloader to also **download the user's stories**,

   - :option:`--highlights`
      to **download the highlights of that profile**,

   - :option:`--tagged`
      to **download posts where the user is tagged**, and

   - :option:`--igtv`
      to **download IGTV videos**.

- ``"#hashtag"``
   Posts with a certain **hashtag** (the quotes are usually necessary).

- ``%location id``
   Posts tagged with a given location; the location ID is the numerical ID
   Instagram labels a location with (e.g.
   \https://www.instagram.com/explore/locations/**362629379**/plymouth-naval-memorial/).
   Requires :option:`--login`.

   .. versionadded:: 4.2

- ``:stories``
   The currently-visible **stories** of your followees (requires
   :option:`--login`).

- ``:feed``
   Your **feed** (requires :option:`--login`).

- ``:saved``
   Posts which are marked as **saved** (requires :option:`--login`).

- ``@profile``
   All profiles that are followed by ``profile``, i.e. the *followees* of
   ``profile`` (requires :option:`--login`).

- ``-post``
   Replace **post** with the post's shortcode to download single post. Must be preceded by ``--`` in
   the argument list to not be mistaken as an option flag::

    instaloader -- -B_K4CykAOtf



   .. versionadded:: 4.1

.. targets-end

Instaloader goes through all media matching the specified targets and
downloads the pictures and videos and their captions. You can specify

- :option:`--comments`
   also **download comments** of each post,

- :option:`--geotags`
   **download geotags** of each post and save them as
   Google Maps link (requires :option:`--login`),

For a reference of all supported command line options, see
:ref:`command-line-options`.

.. _filename-specification:

Filename Specification
^^^^^^^^^^^^^^^^^^^^^^

For each target, Instaloader creates a directory named after the target,
i.e. ``profile``, ``#hashtag``, ``%location id``, ``:feed``, etc. and therein saves the
posts in files named after the post's timestamp.

:option:`--dirname-pattern` allows to configure the directory name of each
target. The default is ``--dirname-pattern={target}``. In the dirname
pattern, the token ``{target}`` is replaced by the target name, and
``{profile}`` is replaced by the owner of the post which is downloaded.

:option:`--filename-pattern` configures the path of the post's files relative
to the target directory that is specified with :option:`--dirname-pattern`.
The default is ``--filename-pattern={date_utc}_UTC``.
The tokens ``{target}`` and ``{profile}`` are replaced like in the
dirname pattern. The following tokens are defined for usage with
:option:`--filename-pattern`:

- ``{target}``
   Target name (as given in Instaloader command line)

- ``{profile}`` (same as ``{owner_username}``)
   Owner of the Post / StoryItem.

- ``{owner_id}``
   Unique integer ID of owner profile.

- ``{shortcode}``
   Shortcode (identifier string).

- ``{mediaid}``
   Integer representation of shortcode.

- ``{filename}``
   Instagram's internal filename.

- ``{date_utc}`` (same as ``{date}``)
   Creation time in UTC timezone.
   `strftime()-style formatting options <https://docs.python.org/3/library/datetime.html#strftime-and-strptime-behavior>`__
   are supported as format specifier. The default date format specifier used by
   Instaloader is::

      {date_utc:%Y-%m-%d_%H-%M-%S}

For example, encode the poster's profile name in the filenames with::

    instaloader --filename-pattern={date_utc}_UTC_{profile} "#hashtag"

As another example, you may instruct Instaloader to store posts in a
``PROFILE/YEAR/SHORTCODE.jpg`` directory structure::

    instaloader --dirname-pattern={profile} --filename-pattern={date_utc:%Y}/{shortcode} <target> ...

.. _filter-posts:

Filter Posts
^^^^^^^^^^^^

.. py:currentmodule:: instaloader

The options :option:`--post-filter` and :option:`--storyitem-filter`
allow to specify criteria that posts or story items have to
meet to be downloaded. If not given, all posts are downloaded.

The filter string must be a
`Python boolean expression <https://docs.python.org/3/reference/expressions.html#boolean-operations>`__
where the attributes from :class:`Post` or
:class:`StoryItem` respectively are defined.

Id est, the following attributes can be used with both
:option:`--post-filter` and :option:`--storyitem-filter`:

- :attr:`~Post.owner_username` (str), :attr:`~Post.owner_id` (int)
   Owner profile username / user ID.

- :attr:`~Post.date_utc` (datetime), :attr:`~Post.date_local` (datetime)
   Creation timestamp. Since :class:`~datetime.datetime` objects can be created
   inside filter strings, this easily allows filtering by creation date. E.g.::

      instaloader --post-filter="date_utc <= datetime(2018, 5, 31)" target

- :attr:`~Post.is_video` (bool)
   Whether Post/StoryItem is a video. For example, you may skip videos::

      instaloader --post-filter="not is_video" target

   This is not the same as :option:`--no-videos` and
   :option:`--no-video-thumbnails`, since sidecar posts (posts that contain
   multiple pictures/videos in one post) have this attribute set to False.

As :option:`--post-filter`, the following attributes can be used additionally:

- :attr:`~Post.viewer_has_liked` (bool)
   Whether user (with :option:`--login`) has liked given post. To download the
   pictures from your feed that you have liked::

      instaloader --login=your_username --post-filter=viewer_has_liked :feed

- :attr:`~Post.likes` (int), :attr:`~Post.comments` (int)
   Likes count / comments count. You might only want to download posts that
   were either liked by yourself or by many others::

      instaloader --login=your_username --post-filter="likes>100 or viewer_has_liked" profile

- :attr:`~Post.caption_hashtags` (list of str) / :attr:`~Post.caption_mentions` (list of str)
   ``#hashtags`` or ``@mentions`` (lowercased) in the Post's caption. For example, to
   download posts of kittens that are cute::

       instaloader --post-filter="'cute' in caption_hashtags" "#kitten"

- :attr:`~Post.tagged_users` (list of str)
   Lowercased usernames that are tagged in the Post.

For :option:`--storyitem-filter`, the following additional attributes are
defined:

- :attr:`~StoryItem.expiring_utc` (datetime) / :attr:`~StoryItem.expiring_local` (datetime)
   Timestamp when StoryItem will get unavailable.

.. _metadata-text-files:

Metadata Text Files
^^^^^^^^^^^^^^^^^^^

Unless :option:`--no-captions` is given, Instaloader creates a ``.txt`` file
along with each post where the Post's caption is saved.

You can customize what metadata to save for each Post or StoryItem with
:option:`--post-metadata-txt` and :option:`--storyitem-metadata-txt`. The
default is ``--post-metadata-txt={caption}`` and no storyitem metadata txt.
These strings are formatted similar as the path patterns described in :ref:`filename-specification` and
the result is saved in text files, unless it is empty.

Specifying these options multiple times results in output having multiple lines,
in the order they were given to Instaloader.

The field names are evaluated to :class:`Post` or :class:`StoryItem` attributes,
and as such, the same fields are supported as in :ref:`filename-specification`
and :ref:`filter-posts`.

For example, to save the current number of likes for each post, rather than
the post's caption::

   instaloader --post-metadata-txt="{likes} likes." <target>

Note that with this feature, it is possible to easily and fastly extract
additional metadata of already-downloaded posts, by reimporting their JSON
files. Say, you now also want to export the number of comments the Posts had
when they were downloaded::

   instaloader --post-metadata-txt="{likes} likes, {comments} comments." <target>/*.json.xz

.. _instaloader-as-cronjob:

Instaloader as Cronjob
^^^^^^^^^^^^^^^^^^^^^^

Instaloader is suitable for running as a cronjob to periodically update your
personal Instagram archive. The :option:`--quiet` option disables user
interactions and logging of non-error messages. To non-interactively use
Instaloader logged-in, create a session file::

   instaloader --login=your_username

Then use the same username in your cronjob to load the session and download
the given targets::

   instaloader --login=your_username --quiet target [...]

Instaloader saves the session file to
``~/.config/instaloader/session-YOUR-USERNAME``. See
:option:`--sessionfile` option for how to override this path.

Programming Instaloader
^^^^^^^^^^^^^^^^^^^^^^^

If your task cannot be done with the command line interface of Instaloader,
consider taking a look at the :ref:`python-module-instaloader`.
Instaloader exposes its internally used methods and structures, making it a
powerful and intuitive Python API for Instagram, allowing to further customize
obtaining media and metadata.

Also see :ref:`codesnippets`, where we collect a few example scripts that use
Instaloader for simple tasks that cannot be done with the command line
interface.
