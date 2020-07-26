Instagram Structures
^^^^^^^^^^^^^^^^^^^^

.. module:: instaloader
   :noindex:

.. highlight:: python

.. contents::
   :backlinks: none

Posts
"""""

.. autoclass:: Post
   :no-show-inheritance:

Additionally, the following trivial structures are defined:

.. autoclass:: PostSidecarNode
   :no-show-inheritance:

.. autoclass:: PostComment
   :no-show-inheritance:

.. autoclass:: PostCommentAnswer
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

Hashtags
""""""""

.. autoclass:: Hashtag
   :no-show-inheritance:

   .. versionadded:: 4.4

TopSearchResults
""""""""""""""""

.. autoclass:: TopSearchResults
   :no-show-inheritance:

   .. versionadded:: 4.3

Loading and Saving
""""""""""""""""""

:class:`Post`, :class:`StoryItem`, :class:`Profile`, :class:`Hashtag` and
:class:`FrozenNodeIterator` can be saved and loaded to/from JSON files.

.. autofunction:: load_structure_from_file

.. autofunction:: save_structure_to_file
