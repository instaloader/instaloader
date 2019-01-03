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
stores all posts along with the pictures's captions there.

.. include:: basic-usage.rst
   :start-after: targets-start
   :end-before: targets-end

- ``filename.json[.xz]``
   Re-Download the given object

- ``+args.txt``
   Read targets (and options) from given textfile. See :option:`+args.txt`.

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

   **Download geotags** when available. Geotags are stored as a text file with
   the location's name and a Google Maps link. This requires an additional
   request to the Instagram server for each picture, which is why it is disabled
   by default.

.. option:: --comments, -C

   Download and update comments for each post. This requires an additional
   request to the Instagram server for each post, which is why it is disabled by
   default.

.. option:: --no-captions

   Do not create txt files.

.. option:: --post-metadata-txt

   Template to write in txt file for each Post. See :ref:`metadata-text-files`.

.. option:: --storyitem-metadata-txt

   Template to write in txt file for each StoryItem. See
   :ref:`metadata-text-files`.

.. option:: --no-metadata-json

   Do not create a JSON file containing the metadata of each post.

.. option:: --no-compress-json

   Do not xz compress JSON files, rather create pretty formatted JSONs.


What to Download of each Profile
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. option:: --profile-pic-only, -P

   .. deprecated:: 4.1
      Use :option:`--no-posts`.

   Only download profile picture.

.. option:: --no-posts

   Do not download regular posts.

   .. versionadded:: 4.1

.. option:: --no-profile-pic

   Do not download profile picture.

.. option:: --stories, -s

   Also **download stories** of each profile that is downloaded. Requires
   :option:`--login`.

.. option:: --highlights

   Also **download highlights** of each profile that is downloaded. Requires
   :option:`--login`.

   .. versionadded:: 4.1

.. option:: --tagged

   Also download posts where each profile is tagged.

   .. versionadded:: 4.1

.. option:: --stories-only

   .. deprecated:: 4.1
      Use :option:`--stories` :option:`--no-posts`.

   Rather than downloading regular posts of each specified profile, only
   download stories.  Requires :option:`--login`. Does not imply
   :option:`--no-profile-pic`.

   .. note::

      If possible, use ``:stories`` target rather than :option:`--stories-only`
      with all your followees. ``:stories`` uses fewer API requests.

Which Posts to Download
^^^^^^^^^^^^^^^^^^^^^^^

.. option:: --fast-update, -F

   For each target, stop when encountering the first already-downloaded picture.
   This flag is recommended when you use Instaloader to update your personal
   Instagram archive.

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

   Do not attempt to download more than COUNT posts.  Applies only to
   ``#hashtag``, ``%location id``, and ``:feed``.


Login (Download Private Profiles)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Instaloader can **login to Instagram**. This allows downloading private
profiles. To login, pass the :option:`--login` option. Your session cookie (not your
password!) will be saved to a local file to be reused next time you want
Instaloader to login.

.. option:: --login YOUR-USERNAME, -l YOUR-USERNAME

   Login name (profile name) for your Instagram account.

.. option:: --sessionfile SESSIONFILE, -f SESSIONFILE

   Path for loading and storing session key file.  Defaults to a path within
   your temporary directory, encoding your local username and your Instagram
   profile name.

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

.. option:: --commit-mode

   Tries to ensure downloaded images avoid corruption in case of unexpected
   interruption. If the last picture is corrupted, Instaloader will fix the
   picture the next time it is run.

   .. versionadded:: 4.2

Miscellaneous Options
^^^^^^^^^^^^^^^^^^^^^

.. option:: --quiet, -q

   Disable user interaction, i.e. do not print messages (except errors) and fail
   if login credentials are needed but not given.
   This is handy for running :ref:`instaloader-as-cronjob`.

.. option:: +args.txt

   Read arguments from file `args.txt`, a shortcut to provide arguments from
   file rather than command-line. This provides a convenient way to hide login
   info from CLI, and can also be used to simplify managment of long arguments.

   .. note::

      Text file should separate arguments with line breaks.

      args.txt example::

         --login=MYUSERNAME
         --password=MYPASSWORD
         --fast-update
         profile1
         profile2

   .. versionadded:: 4.1
