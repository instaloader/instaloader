.. meta::
   :description:
      Documentation of Instaloader module, a powerful and intuitive
      Python library to download Instagram media and metadata.

.. _python-module-instaloader:

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

:class:`Post` instances can be created with:

- :func:`Post.from_shortcode`
   Use a Post shortcode (part of the Post URL,
   ``https://www.instagram.com/p/SHORTCODE/``) to create a Post
   object::

      post = Post.from_shortcode(L.context, SHORTCODE)

- :meth:`Profile.get_posts`
   All media of a :class:`Profile`.

- :meth:`Profile.get_saved_posts`
   Media that the user marked as saved (:class:`Profile` must be own profile
   for this to work)

- :meth:`Instaloader.get_feed_posts`
   Media in the user's feed.

- :meth:`Instaloader.get_explore_posts`
   Media that is suggested by Instagram to explore.

- :meth:`Instaloader.get_hashtag_posts`
   Media associated with given hashtag.

With the :class:`Profile` class, Instaloader also makes it easy to access
metadata of a Profile. :class:`Profile` instances can be created with:

- :meth:`Profile.from_username`::

     profile = Profile.from_username(L.context, USERNAME)

- :meth:`Profile.from_id`
   given its User ID. This allows to easily lookup a Profile's username given
   its ID::

      Profile.from_id(L.context, USERID).username

- :meth:`Profile.get_followees`
   Profiles that are followed by given user.

- :meth:`Profile.get_followers`
   Profiles that follow given user.

- :attr:`Post.owner_profile`, :attr:`Story.owner_profile` and :attr:`StoryItem.owner_profile`
   Owner profile of particular object.

- :meth:`Post.get_likes`
   Profiles that liked a given :class:`Post`

- :attr:`PostComment.owner` attribute for comment in :meth:`Post.get_comments`
   Profile of a Post comment.

A reference of the many methods provided by the :mod:`instaloader` module is
provided in the remainder of this document.

For a list of real code examples using the Instaloader module for advanced
tasks, see :ref:`codesnippets`.

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

.. autoclass:: PostComment
   :no-show-inheritance:

.. autoclass:: PostLocation
   :no-show-inheritance:

User Stories
""""""""""""

.. autoclass:: Story
   :no-show-inheritance:

.. autoclass:: StoryItem
   :no-show-inheritance:

Highlights
""""""""""

.. autoclass:: Highlight
   :no-show-inheritance:
   :inherited-members:

   Bases: :class:`Story`

   .. versionadded:: 4.1

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

.. currentmodule:: instaloader.exceptions

.. autoexception:: InstaloaderException
   :no-show-inheritance:

.. autoexception:: ConnectionException

.. currentmodule:: instaloader

.. autoexception:: QueryReturnedBadRequestException

.. autoexception:: QueryReturnedNotFoundException

.. autoexception:: QueryReturnedForbiddenException

.. autoexception:: ProfileNotExistsException

.. autoexception:: ProfileHasNoPicsException

.. autoexception:: PrivateProfileNotFollowedException

.. autoexception:: LoginRequiredException

.. autoexception:: TwoFactorAuthRequiredException

   .. versionadded:: 4.2

.. autoexception:: InvalidArgumentException

.. autoexception:: BadResponseException

.. autoexception:: BadCredentialsException

.. autoexception:: TooManyRequestsException

``InstaloaderContext`` (Low-level functions)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: InstaloaderContext
   :no-show-inheritance:
