.. _codesnippets:

Advanced Instaloader Examples
=============================

.. currentmodule:: instaloader

.. highlight:: python

.. contents::
   :backlinks: none

Here we present code examples that use the :ref:`python-module-instaloader` for
more advanced tasks than what is possible with the Instaloader command line
interface.

.. For each code snippet:
   - title
   - brief description of what it does / motivation / how it works
   - code, or link to code
   - link to discussion issue
   - link used methods

Download Posts in a specific period
-----------------------------------

To collect pictures (and metadata) only from a specific period, you can play
around with :func:`~itertools.dropwhile` and :func:`~itertools.takewhile` from
:mod:`itertools` like in this snippet.

.. literalinclude:: codesnippets/121_since_until.py

See also :class:`Post`, :meth:`Instaloader.download_post`.

Discussed in :issue:`121`.

Likes of a Profile / Ghost Followers
------------------------------------

To store inactive followers, i.e. followers that did not like any of your
pictures, into a file you can use this approach.

.. literalinclude:: codesnippets/120_ghost_followers.py

See also :meth:`Profile.get_posts`, :meth:`Post.get_likes`,
:meth:`Profile.get_followers`, :meth:`Instaloader.load_session_from_file`,
:meth:`Profile.from_username`.

Discussed in :issue:`120`.

Track Deleted Posts
-------------------

This script uses Instaloader to obtain a list of currently-online posts, and
generates the matching filename of each post. It outputs a list of posts which
are online but not offline (i.e. not yet downloaded) and a list of posts which
are offline but not online (i.e. deleted in the profile).

.. literalinclude:: codesnippets/56_track_deleted.py

See also :func:`load_structure_from_file`, :meth:`Profile.from_username`,
:meth:`Profile.get_posts`, :class:`Post`.

Discussed in :issue:`56`.

Only one Post per User
----------------------

To download only the one most recent post from each user, this snippet creates a
:class:`set` that contains the users of which a post has already been
downloaded. When iterating the posts, check whether the post's owner already is
in the set. If so, skip the post. Otherwise, download it and add the user to
that set.

.. literalinclude:: codesnippets/113_only_one_per_user.py

See also :class:`Post`, :meth:`Instaloader.download_post`,
:attr:`Post.owner_profile`, :class:`Profile`.

Discussed in :issue:`113`.

Upgrade Images by local Copies
------------------------------

The following script finds local versions of images fetched by Instaloader, in
order to ugprade the downloaded images by locally-found versions with better
quality. It uses image hashing to identify similar images.

`updgrade-instaloader-images.py <https://gist.github.com/pavelkryukov/15f93d19a99428a284a8bcec27e0187b>`__ (external link to GitHub Gist)

Discussed in :issue:`46`.

Render Captions to downloaded Images
------------------------------------

Instaloader does not modify the downloaded JPEG file. However, one could combine
it with an imaging library such as Pillow or PIL to render the
:attr:`Post.caption` on pictures.  The following shows an approach.

.. literalinclude:: codesnippets/110_pil_captions.py

See also :attr:`Post.caption`, :attr:`Post.url`, :meth:`Post.from_shortcode`,
:func:`load_structure_from_file`.

Discussed in :issue:`110`.
