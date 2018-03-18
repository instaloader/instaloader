.. meta::
   :description:
      Instaloader can also be used as a powerful and easy-to-use
      Python API for Instagram, allowing to download media and metadata.

Python Module :mod:`instaloader`
--------------------------------

.. module:: instaloader

.. highlight:: python

Instaloader exposes its internally used methods as a Python module, making it a
**powerful and easy-to-use Python API for Instagram**, allowing to further
customize obtaining media and metadata.

Start with getting an instance of :class:`Instaloader`::

    import instaloader

    # Get instance
    L = instaloader.Instaloader()

    # Optionally, login or load session
    L.login(USER, PASSWORD)        # (login)
    L.interactive_login(USER)      # (ask password on terminal)
    L.load_session_from_file(USER) # (load session created w/
                                   #  `instaloader -l USERNAME`)

:mod:`instaloader` provides the :class:`Post` structure, which represents a
picture, video or sidecar (set of multiple pictures/videos) posted in a user's
profile. :class:`Instaloader` provides methods to iterate over Posts from a
certain source::

    for post in L.get_hashtag_posts('cat'):
        # post is an instance of instaloader.Post
        L.download_post(post, target='#cat')

Besides :func:`Instaloader.get_hashtag_posts`, there is
:func:`Instaloader.get_feed_posts`, :func:`Instaloader.get_profile_posts` and
:func:`Instaloader.get_saved_posts`.
Also, :class:`Post` instances can be created with :func:`Post.from_shortcode`
and :func:`Post.from_mediaid`.

Further, information about profiles can be easily obtained. For example, you may
print a list of all followees and followers of a profile with::

    # Print followees
    print(PROFILE + " follows these profiles:")
    for f in L.get_followees(PROFILE):
        print("\t%s\t%s" % (f['username'], f['full_name']))

    # Print followers
    print("Followers of " + PROFILE + ":")
    for f in L.get_followers(PROFILE):
        print("\t%s\t%s" % (f['username'], f['full_name']))

Then, you may download all pictures of all followees with::

    for f in L.get_followees(PROFILE):
        L.download_profile(f['username'])

Each Instagram profile has its own unique ID which stays unmodified even if a
user changes his/her username. To get said ID, given the profile's name, you may
call::

    L.get_id_by_username(PROFILE_NAME)

A reference of the many methods provided by the :mod:`instaloader` module is
provided in the remainder of this document. Feel free to direct any issue or
contribution to
`Instaloader on Github <https://github.com/instaloader/instaloader>`__.

``Instaloader`` (Main Class)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: Instaloader
   :no-show-inheritance:

``Post`` Class
^^^^^^^^^^^^^^

.. autoclass:: Post
   :no-show-inheritance:

Miscellaneous Functions
^^^^^^^^^^^^^^^^^^^^^^^

.. autofunction:: shortcode_to_mediaid

.. autofunction:: mediaid_to_shortcode

.. autoclass:: Tristate

Exceptions
^^^^^^^^^^

.. autoexception:: InstaloaderException
   :no-show-inheritance:

.. autoexception:: QueryReturnedNotFoundException

.. autoexception:: QueryReturnedForbiddenException

.. autoexception:: ProfileNotExistsException

.. autoexception:: ProfileHasNoPicsException

.. autoexception:: PrivateProfileNotFollowedException

.. autoexception:: LoginRequiredException

.. autoexception:: InvalidArgumentException

.. autoexception:: BadResponseException

.. autoexception:: BadCredentialsException

.. autoexception:: ConnectionException

.. autoexception:: TooManyRequestsException
