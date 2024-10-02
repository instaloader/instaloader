.. _command-line-options:

Command Line Options
====================

Instaloader is invoked with::

   $ instaloader [options] target [target ...]

where ``target`` is a ``profile``, a ``"#hashtag"``, ``@profile`` (all profiles
that *profile* is following), ``%location ID``, or if logged in ``:feed`` (pictures from your
feed), ``:stories`` (stories of your followees) or ``:saved`` (collection of
posts marked as saved).

Here we explain the additional options that can be given to Instaloader to
customize its behavior.  For an
introduction on how to use Instaloader, see
:ref:`download-pictures-from-instagram`.

To get a list of all flags, their abbreviations and
their descriptions, you may also run::

   instaloader --help

Targets
^^^^^^^

Specify a list of targets. For each of these, Instaloader creates a folder and
stores all posts along with the pictures' captions there.

.. include:: basic-usage.rst
   :start-after: targets-start
   :end-before: targets-end

- ``filename.json[.xz]``
   Re-Download the given object

- ``+args.txt``
   Read targets (and options) from given text file. See :option:`+args.txt`.

What to Download of each Post
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. option:: --no-pictures

   Do not download post pictures. Cannot be used together with
   :option:`--fast-update`. Implies :option:`--no-video-thumbnails`, does not
   imply :option:`--no-videos`.

   .. versionadded:: 4.1

.. option:: --no-videos, -V

   Do not download videos.

.. option:: --no-video-thumbnails

   Do not download thumbnails of videos.

.. option:: --geotags, -G

   Download geotags when available. Geotags are stored as a text file with
   the location's name and a Google Maps link. This requires an additional
   request to the Instagram server for each picture. Requires :ref:`login<login>`.

.. option:: --comments, -C

   Download and update comments for each post. This requires an additional
   request to the Instagram server for each post, which is why it is disabled by
   default. Requires :ref:`login<login>`.

.. option:: --no-captions

   Do not create txt files.

.. option:: --post-metadata-txt

   Template to write in txt file for each Post. See :ref:`metadata-text-files`.

.. option:: --storyitem-metadata-txt

   Template to write in txt file for each StoryItem. See
   :ref:`metadata-text-files`.

.. option:: --slide

   Download only selected images of a sidecar. You can select single images using their
   index in the sidecar starting with the leftmost or you can specify a range of images
   with the following syntax: ``start_index-end_index``. Example:
   ``--slide 1`` will select only the first image, ``--slide last`` only the last one and ``--slide 1-3`` will select only
   the first three images.

   .. versionadded:: 4.6

.. option:: --no-metadata-json

   Do not create a JSON file containing the metadata of each post.

.. option:: --no-compress-json

   Do not xz compress JSON files, rather create pretty formatted JSONs.

What to Download of each Profile
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. option:: --no-posts

   Do not download regular posts.

   .. versionadded:: 4.1

.. option:: --no-profile-pic

   Do not download profile picture.

.. option:: --stories, -s

   Also download stories of each profile that is downloaded. Requires
   :ref:`login<login>`.

.. option:: --highlights

   Also download highlights of each profile that is downloaded. Requires
   :ref:`login<login>`.

   .. versionadded:: 4.1

.. option:: --tagged

   Also download posts where each profile is tagged.

   .. versionadded:: 4.1

.. option:: --reels

   Also download Reels videos.

   .. versionadded:: 4.14

.. option:: --igtv

   Also download IGTV videos.

   .. versionadded:: 4.3

Which Posts to Download
^^^^^^^^^^^^^^^^^^^^^^^

.. option:: --fast-update, -F

   For each target, stop when encountering the first already-downloaded picture.
   This flag is recommended when you use Instaloader to update your personal
   Instagram archive.

.. option:: --latest-stamps [STAMPSFILE]

   Works similarly to :option:`--fast-update`, but instead of relying on already
   downloaded media, the time each profile was downloaded is stored, and only
   media newer than the last download is fetched. This allows updating your
   personal Instagram archive while emptying the target directories.

   Only works for media associated with a specific profile, and that is returned
   in chronological order: profile posts, profile stories, profile IGTV posts
   and profile tagged posts.

   By default, the information is stored in
   ``~/.config/instaloader/latest-stamps.ini``, but you can specify an
   alternative location.

   .. versionadded:: 4.8

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

.. option:: --count COUNT, -c

   Do not attempt to download more than COUNT posts.  Applies to
   ``#hashtag``, ``%location_id``, ``:feed``, and ``:saved``.

.. _login:

Login (Download Private Profiles)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Instaloader can login to Instagram. This allows downloading private
profiles. To login, pass the :option:`--login` option. Your session cookie (not your
password!) will be saved to a local file to be reused next time you want
Instaloader to login.

Instead of :option:`--login`, it is possible to use
:option:`--load-cookies` to import a session from a browser.

.. option:: --login YOUR-USERNAME, -l YOUR-USERNAME

   Login name (profile name) for your Instagram account.

.. option:: --load-cookies BROWSER-NAME, -b BROWSER-NAME

   Use Instagram cookie in your browser to login.
   This feature requires the browser_cookie3 library.
   Compatible with :option:`--cookiefile` if you want to load cookies from browser profiles.
   Incompatible with :option:`--login` due to potential username mismatch between user input and browser login.
   Supported browsers: Brave, Chrome, Chromium, Edge, Firefox, LibreWolf, Opera, Opera_GX, Safari and Vivaldi.

   In subsequent runs, you can just use :option:`--login` to reuse the
   same session, which is saved by Instaloader.

   .. versionadded:: 4.11

.. option:: --cookiefile COOKIE-FILE, -B COOKIE-FILE

   Cookie file path of a browser profile to load cookies from.

  .. versionadded:: 4.11

.. option:: --sessionfile SESSIONFILE, -f SESSIONFILE

   Path for loading and storing session key file.  Defaults to
   ``~/.config/instaloader/session-YOUR-USERNAME``.

.. option:: --password YOUR-PASSWORD, -p YOUR-PASSWORD

   Password for your Instagram account.  Without this option, you'll be prompted
   for your password interactively if there is not yet a valid session file.

   .. warning:: Using :option:`--password` option is discouraged for security
      reasons.  Enter your password interactively when asked, or use the
      sessionfile feature (:option:`--sessionfile` to customize path).

How to Download
^^^^^^^^^^^^^^^

.. option:: --dirname-pattern DIRNAME_PATTERN

   Name of directory where to store posts. ``{profile}`` is replaced by the
   profile name, ``{target}`` is replaced by the target you specified, i.e.
   either ``:feed``, ``#hashtag`` or the profile name. Defaults to ``{target}``.
   See :ref:`filename-specification`.

.. option:: --filename-pattern FILENAME_PATTERN

   Prefix of filenames for posts and stories, relative to the directory given with
   :option:`--dirname-pattern`. ``{profile}`` is replaced by the profile name,
   ``{target}`` is replaced by the target you specified, i.e.  either ``:feed``,
   ``#hashtag`` or the profile name. Defaults to ``{date_utc}_UTC``.
   See :ref:`filename-specification` for a list of supported tokens.

.. option:: --title-pattern TITLE_PATTERN

   Prefix of filenames for profile pics, hashtag profile pics, and highlight
   covers, relative to the directory given with :option:`--dirname-pattern`.
   Defaults to ``{date_utc}_UTC_{typename}`` if :option:`--dirname-pattern`
   contains ``{target}`` or ``{profile}``, otherwise defaults to
   ``{target}_{date_utc}_UTC_{typename}``.
   See :ref:`filename-specification` for a list of supported tokens.

   .. versionadded:: 4.8

.. option:: --sanitize-paths

   Force sanitization of paths so that the resulting file and directory names
   are valid on both Windows and Unix.

   .. versionadded:: 4.9

.. option:: --resume-prefix prefix

   For many targets, Instaloader is capable of resuming a previously-aborted
   download loop.  To do so, it creates a JSON file within the target directory
   when interrupted.  This option controls the prefix for filenames that are
   used to save the information to resume an interrupted download.  The default
   prefix is ``iterator``.

   Resuming an interrupted download is supported for the following targets:
    - Profile posts,
    - Profile IGTV posts (:option:`--igtv`),
    - Profile tagged posts (:option:`--tagged`),
    - Saved posts (``:saved``),
    - Hashtags.

   This feature is enabled by default for targets where it is supported;
   :option:`--resume-prefix` only changes the name of the iterator files.

   To turn this feature off, use :option:`--no-resume`.

   JSON files with resume information are always compressed, regardless of
   :option:`--no-compress-json`.

   .. versionadded:: 4.5

.. option:: --no-resume

   Do not resume a previously-aborted download iteration, and do not save such
   information when interrupted.

   .. versionadded:: 4.5

.. option:: --user-agent USER_AGENT

   User Agent to use for HTTP requests. Per default, Instaloader pretends being
   Chrome/127 on Linux.

.. option:: --max-connection-attempts N

   Maximum number of connection attempts until a request is aborted. Defaults
   to ``3``. If a connection fails, it can be manually skipped by hitting
   :kbd:`Control-c`. Set this to ``0`` to retry infinitely.

.. option:: --request-timeout N

   Seconds to wait before timing out a connection request. Defaults to 300.

   .. versionadded:: 4.3

   .. versionchanged:: 4.6
      Enabled this option by default with a timeout of 300 seconds.

.. option:: --abort-on STATUS_CODE_LIST

   Comma-separated list of HTTP status codes that cause Instaloader to abort,
   bypassing all retry logic.

   For example, with ``--abort-on=302,400,429``, Instaloader will stop if a
   request is responded with a 302 redirect, a Bad Request error, or a Too Many
   Requests error.

   .. versionadded:: 4.7

.. option:: --no-iphone

   Do not attempt to download iPhone version of images and videos.

   .. versionadded:: 4.8

Miscellaneous Options
^^^^^^^^^^^^^^^^^^^^^

.. option:: --quiet, -q

   Disable user interaction, i.e. do not print messages (except errors) and fail
   if login credentials are needed but not given.
   This is handy for running :ref:`instaloader-as-cronjob`.

.. option:: +args.txt

   Read arguments from file `args.txt`, a shortcut to provide arguments from
   file rather than command-line. This provides a convenient way to hide login
   info from CLI, and can also be used to simplify management of long arguments.
   You can provide more than one file at once, e.g.: ``+args1.txt +args2.txt``.

   .. note::

      Text file should separate arguments with line breaks.

   `args.txt` example::

      --login=MYUSERNAME
      --password=MYPASSWORD
      --fast-update
      profile1
      profile2

   .. versionadded:: 4.1
