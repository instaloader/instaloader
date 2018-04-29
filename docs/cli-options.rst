Command Line Options
====================

Instaloader is invoked with::

   $ instaloader [options] target [target ...]

where ``target`` is a ``profile``, a ``"#hashtag"``, ``@profile`` (all profiles
that *profile* is following), or if logged in ``:feed`` (pictures from your
feed), ``:stories`` (stories of your followees) or ``:saved`` (collection of
posts marked as saved).

Here we explain the additional options that can be given to Instaloader to
customize its behavior.  To get a list of all flags, their abbreviations and
their descriptions, you may also run ``instaloader --help``.

What to Download
^^^^^^^^^^^^^^^^

Specify a list of targets (profiles, #hashtags, ``:feed``, ``:stories`` or
``:saved``). For each of these, Instaloader creates a folder and stores all
posts along with the pictures's captions and the current **profile picture**
there. If an already-downloaded profile has been renamed, Instaloader
automatically **finds it by its unique ID** and renames the folder likewise.

.. option:: --profile-pic-only

   Only download profile picture.

.. option:: --no-profile-pic

   Do not download profile picture.

.. option:: --no-videos

   Do not download videos.

.. option:: --no-video-thumbnails

   Do not download thumbnails of videos.

.. option:: --geotags

   **Download geotags** when available. Geotags are stored as a text file with
   the location's name and a Google Maps link. This requires an additional
   request to the Instagram server for each picture, which is why it is disabled
   by default.

.. option:: --comments

   Download and update comments for each post. This requires an additional
   request to the Instagram server for each post, which is why it is disabled by
   default.

.. option:: --no-captions

   Do not create txt files.

.. option:: --post-metadata-txt

   Template to write in txt file for each Post.

.. option:: --storyitem-metadata-txt

   Template to write in txt file for each StoryItem.

.. option:: --stories

   Also **download stories** of each profile that is downloaded. Requires
   :option:`--login`.

.. option:: --no-metadata-json

   Do not create a JSON file containing the metadata of each post.

.. option:: --no-compress-json

   Do not xz compress JSON files, rather create pretty formatted JSONs.

.. option:: --stories-only

   Rather than downloading regular posts of each specified profile, only
   download stories.  Requires :option:`--login`. Does not imply
   :option:`--no-profile-pic`.

.. option:: --post-filter filter, --only-if filter

   Expression that, if given, must evaluate to True for each post to be
   downloaded.  Must be a syntactically valid Python expression. Variables are
   evaluated to :class:`instaloader.Post` attributes.  Example:
   ``--post-filter=viewer_has_liked``. See :ref:`filter-posts` for more
   examples.

.. option:: --storyitem-filter filter

   Expression that, if given, must evaluate to True for each storyitem to be
   downloaded.  Must be a syntactically valid Python expression. Variables are
   evaluated to :class:`instaloader.StoryItem` attributes.
   See :ref:`filter-posts` for more examples.



When to Stop Downloading
^^^^^^^^^^^^^^^^^^^^^^^^

If none of these options are given, Instaloader goes through all pictures
matching the specified targets.

.. option:: --fast-update

   For each target, stop when encountering the first already-downloaded picture.
   This flag is recommended when you use Instaloader to update your personal
   Instagram archive.

.. option:: --count COUNT

   Do not attempt to download more than COUNT posts.  Applies only to
   ``#hashtag`` and ``:feed``.


Login (Download Private Profiles)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Instaloader can **login to Instagram**. This allows downloading private
profiles. To login, pass the :option:`--login` option. Your session cookie (not your
password!) will be saved to a local file to be reused next time you want
Instaloader to login.

.. option:: --login YOUR-USERNAME

   Login name (profile name) for your Instagram account.

.. option:: --sessionfile SESSIONFILE

   Path for loading and storing session key file.  Defaults to a path within
   your temporary directory, encoding your local username and your Instagram
   profile name.

.. option:: --password YOUR-PASSWORD

   Password for your Instagram account.  Without this option, you'll be prompted
   for your password interactively if there is not yet a valid session file.

How to Download
^^^^^^^^^^^^^^^

.. option:: --dirname-pattern DIRNAME_PATTERN

   Name of directory where to store posts. ``{profile}`` is replaced by the
   profile name, ``{target}`` is replaced by the target you specified, i.e.
   either ``:feed``, ``#hashtag`` or the profile name. Defaults to ``{target}``.
   See :ref:`filename-specification`.

.. option:: --filename-pattern FILENAME_PATTERN

   Prefix of filenames, relative to the directory given with
   :option:`--dirname-pattern`. ``{profile}`` is replaced by the profile name,
   ``{target}`` is replaced by the target you specified, i.e.  either ``:feed``,
   ``#hashtag`` or the profile name. Defaults to ``{date_utc}_UTC``.
   See :ref:`filename-specification` for a list of supported tokens.

.. option:: --user-agent USER_AGENT

   User Agent to use for HTTP requests. Per default, Instaloader pretends being
   Chrome/51.

.. option:: --max-connection-attempts N

   Maximum number of connection attempts until a request is aborted. Defaults
   to ``3``. If a connection fails, it can be manually skipped by hitting
   :kbd:`Control-c`. Set this to ``0`` to retry infinitely.

Miscellaneous Options
^^^^^^^^^^^^^^^^^^^^^

.. option:: --quiet

   Disable user interaction, i.e. do not print messages (except errors) and fail
   if login credentials are needed but not given. This makes Instaloader
   **suitable as a cron job**.
