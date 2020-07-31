.. _codesnippets:

Advanced Instaloader Examples
=============================

.. currentmodule:: instaloader

.. highlight:: python

.. contents::
   :backlinks: none

Here we present code examples that use the :ref:`python-module-instaloader` for
more advanced Instagram downloading or metadata mining than what is possible
with the Instaloader command line interface.

The scripts presented here can be downloaded from our source tree:
`instaloader/docs/codesnippets/ <https://github.com/instaloader/instaloader/tree/master/docs/codesnippets>`__

.. For each code snippet:
   - title
   - brief description of what it does / motivation / how it works
   - code, or link to code
   - link to discussion issue
   - link used methods

Download Posts in a Specific Period
-----------------------------------

To only download Instagram pictures (and metadata) that are within a specific
period, you can simply use :func:`~itertools.dropwhile` and
:func:`~itertools.takewhile` from :mod:`itertools` on a generator that returns
Posts in **exact chronological order**, such as :meth:`Profile.get_posts`.

.. literalinclude:: codesnippets/121_since_until.py

See also :class:`Post`, :meth:`Instaloader.download_post`.

Discussed in :issue:`121`.

The code example with :func:`~itertools.dropwhile` and
:func:`~itertools.takewhile` makes the assumption that the post iterator returns
posts in exact chronological order.  As discussed in :issue:`666`, the following
approach fits for an **almost chronological order**, where up to *k* older posts
are inserted into an otherwise chronological order, such as a Hashtag feed.

.. literalinclude:: codesnippets/666_historical_hashtag_data.py

Likes of a Profile / Ghost Followers
------------------------------------

To obtain a list of your inactive followers, i.e. followers that did not like
any of your pictures, you can use this approach.

.. literalinclude:: codesnippets/120_ghost_followers.py

See also :meth:`Profile.get_posts`, :meth:`Post.get_likes`,
:meth:`Profile.get_followers`, :meth:`Instaloader.load_session_from_file`,
:meth:`Profile.from_username`.

Discussed in :issue:`120`.

Track Deleted Posts
-------------------

This script uses Instaloader to obtain a list of currently-online Instagram and
compares it with the set of posts that you already have downloaded.  It outputs
a list of posts which are online but not offline (i.e. not yet downloaded) and a
list of posts which are offline but not online (i.e. deleted in the profile).

.. literalinclude:: codesnippets/56_track_deleted.py

See also :func:`load_structure_from_file`, :meth:`Profile.from_username`,
:meth:`Profile.get_posts`, :class:`Post`.

Discussed in :issue:`56`.

Only one Post per User
----------------------

To download only the single most recent post per user within a hashtag feed,
this snippet uses a :class:`set` that contains the users of whom a post has
already been downloaded. For each post, it checks whether the post's creator is
already contained in that set. If not, the post is downloaded from Instagram and
the user is added to that set.

.. literalinclude:: codesnippets/113_only_one_per_user.py

See also :class:`Post`, :meth:`Instaloader.download_post`,
:attr:`Post.owner_profile`, :class:`Profile`.

Discussed in :issue:`113`.

Top X Posts of User
-------------------

With Instaloader, it is easy to download the few most-liked pictures of a user.

.. literalinclude:: codesnippets/194_top_x_of_user.py

Discussed in :issue:`194`.

Metadata JSON Files
-------------------

The JSON files Instaloader saves along with each Post contain all the metadata
that has been retrieved from Instagram while downloading the picture and
associated required information.

With `jq <https://stedolan.github.io/jq/>`__, a command-line JSON processor, the
metadata can be easily post-processed. For example, Instaloader's JSON files can
be pretty-formatted with:

.. code-block:: none

   xzcat 2018-05-13_11-18-45_UTC.json.xz | jq .node

However, Instaloader tries to do as few metadata requests as possible, so,
depending on how Instaloader has been invoked, it may occur that these files do
not contain the complete available metadata structure. Nevertheless, the file
can be loaded into Instaloader with :func:`load_structure_from_file` and the
required metadata then be accessed via the :class:`Post` or :class:`Profile`
attributes, which trigger an Instagram request if that particular information is
not present in the JSON file.
