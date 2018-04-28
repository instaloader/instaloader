.. meta::
   :description:
      Documentation of Instaloader module, a powerful and intuitive
      Python library to download Instagram media and metadata.

Python Module :mod:`instaloader`
--------------------------------

.. module:: instaloader

.. highlight:: python

.. contents::
  :backlinks: none

Instaloader exposes its internally used methods and structures as a Python
module, making it a **powerful and intuitive Python API for Instagram**,
allowing to further customize obtaining media and metadata.

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
:func:`Instaloader.get_feed_posts`, :func:`Profile.get_posts` and
:func:`Profile.get_saved_posts`.
Also, :class:`Post` instances can be created with :func:`Post.from_shortcode`
and :func:`Post.from_mediaid`.

A reference of the many methods provided by the :mod:`instaloader` module is
provided in the remainder of this document.

``Instaloader`` (Main Class)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: Instaloader
   :no-show-inheritance:

Instagram Structures
^^^^^^^^^^^^^^^^^^^^

Posts
"""""

.. autoclass:: Post
   :no-show-inheritance:

Additionally, the following trivial structures are defined:

.. autoclass:: PostSidecarNode
   :no-show-inheritance:
   :no-members:

.. autoclass:: PostComment
   :no-show-inheritance:
   :no-members:

.. autoclass:: PostLocation
   :no-show-inheritance:
   :no-members:

User Stories
""""""""""""

.. autoclass:: Story
   :no-show-inheritance:

.. autoclass:: StoryItem
   :no-show-inheritance:

Profiles
""""""""

.. autoclass:: Profile
   :no-show-inheritance:

Loading and Saving
""""""""""""""""""

:class:`Post`, :class:`StoryItem` and :class:`Profile` can be saved and loaded
to/from JSON files.

.. autofunction:: load_structure_from_file

.. autofunction:: save_structure_to_file

Exceptions
^^^^^^^^^^

.. autoexception:: InstaloaderException
   :no-show-inheritance:

.. autoexception:: QueryReturnedBadRequestException

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

``InstaloaderContext`` (Low-level functions)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: InstaloaderContext
   :no-show-inheritance:
