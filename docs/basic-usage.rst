Download Pictures from Instagram
---------------------------------

.. highlight:: none

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
first already-downloaded picture. When updating profiles, Instaloader
automatically **detects profile name changes** and renames the target directory
accordingly.

Instaloader can also be used to **download private profiles**. To do so,
invoke it with

::

    instaloader --login=your_username profile [profile ...]

When logging in, Instaloader **stores the session cookies** in a file in your
temporary directory, which will be reused later the next time :option:`--login`
is given.  So you can download private profiles **non-interactively** when you
already have a valid session cookie file.

.. _what-to-download:

What to Download
^^^^^^^^^^^^^^^^

Instaloader supports the following targets:

``profile``
   Public profile, or private profile with :option:`--login`. For each profile
   you download, :option:`--stories` instructs Instaloader to also
   **download the user's stories**.

``"#hashtag"``
   Posts with a certain **hashtag** (the quotes are usually neccessary),

``:stories``
   The currently-visible **stories** of your followees (requires
   :option:`--login`),

``:feed``
   Your **feed** (requires :option:`--login`),

``@profile``
   All profiles that are followed by ``profile``, i.e. the *followees* of
   ``profile`` (requires :option:`--login`).

Instaloader goes through all media matching the specified targets and
downloads the pictures and videos and their captions. You can specify

- :option:`--comments`, to also **download comments** of each post,

- :option:`--geotags`, to **download geotags** of each post and save them as
  Google Maps link,

- :option:`--metadata-json`, to store further post metadata in a separate JSON
  file.

.. _filename-specification:

Filename Specification
^^^^^^^^^^^^^^^^^^^^^^

For each target, Instaloader creates a directory named after the target,
i.e. ``profile``, ``#hashtag``, ``:feed``, etc. and therein saves the
posts in files named after the post's timestamp.

:option:`--dirname-pattern` allows to configure the directory name of each
target. The default is ``--dirname-pattern={target}``. In the dirname
pattern, the token ``{target}`` is replaced by the target name, and
``{profile}`` is replaced by the owner of the post which is downloaded.

:option:`--filename-pattern` configures the path of the post's files relative
to the target directory. The default is ``--filename-pattern={date}``.
The tokens ``{target}`` and ``{profile}`` are replaced like in the
dirname pattern. Further, the tokens ``{date}`` and ``{shortcode}`` are
defined. Additionally, in case of not downloading stories, the attributes of
:class:`.Post` can be used, e.g. ``{post.owner_id}`` or ``{post.mediaid}``.

For example, encode the poster's profile name in the filenames with:

::

    instaloader --filename-pattern={date}_{profile} "#hashtag"

The pattern string is formatted with Python's string formatter. This
gives additional flexibilty for pattern specification. For example,
`strftime-style formatting options <https://docs.python.org/3/library/datetime.html#strftime-and-strptime-behavior>`__
are supported for the post's
timestamp. The default for ``{date}`` is ``{date:%Y-%m-%d_%H-%M-%S}``.

.. _filter-posts:

Filter Posts
^^^^^^^^^^^^

The :option:`--only-if` option allows to specify criterias that posts have to
meet to be downloaded. If not given, all posts are downloaded. It must be a
boolean Python expression where the variables :attr:`.likes`, :attr:`.comments`,
:attr:`.viewer_has_liked`, :attr:`.is_video`, and many more are defined.

A few examples:

To **download the pictures from your feed that you have liked**:

::

    instaloader --login=your_username --only-if=viewer_has_liked :feed

Or you might only want to download **posts that either you liked or were
liked by many others**:

::

    instaloader --login=your_username --only-if="likes>100 or viewer_has_liked" profile

Or you may **skip videos**:

::

    instaloader --only-if="not is_video" target

Or you may filter by hashtags that occur in the Post's caption. For
example, to download posts of kittens that are cute: ::

    instaloader --only-if="'cute' in caption_hashtags" "#kitten"

The given string is evaluated as a
`Python boolean expression <https://docs.python.org/3/reference/expressions.html#boolean-operations>`__,
where all occuring variables are attributes of the :class:`.Post` class.
