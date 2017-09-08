Python Module :mod:`instaloader`
--------------------------------

.. module:: instaloader

.. highlight:: python

You may also use parts of Instaloader as library to do other interesting
things.

For example, to get a list of all followees and a list of all followers of a profile, do

.. code:: python

    import instaloader

    # Get instance
    loader = instaloader.Instaloader()

    # Login
    loader.interactive_login(USERNAME)

    # Print followees
    print(PROFILE + " follows these profiles:")
    for f in loader.get_followees(PROFILE):
        print("\t%s\t%s" % (f['username'], f['full_name']))

    # Print followers
    print("Followers of " + PROFILE + ":")
    for f in loader.get_followers(PROFILE):
        print("\t%s\t%s" % (f['username'], f['full_name']))

Then, you may download all pictures of all followees with

.. code:: python

    for f in loader.get_followees(PROFILE):
        loader.download_profile(f['username'])

You could also download your last 20 liked pics with

.. code:: python

    loader.download_feed_posts(max_count=20, fast_update=True,
                               filter_func=lambda post: post.viewer_has_liked)

To download the last 20 pictures with hashtag #cat, do

.. code:: python

    loader.download_hashtag('cat', max_count=20)

Generally, :class:`Instaloader` provides methods to iterate over the Posts from
a certain source.

.. code:: python

    for post in loader.get_hashtag_posts('cat'):
        # post is an instance of instaloader.Post
        loader.download_post(post, target='#cat')

Each Instagram profile has its own unique ID which stays unmodified even
if a user changes his/her username. To get said ID, given the profile's
name, you may call

.. code:: python

    loader.get_id_by_username(PROFILE_NAME)


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

.. autoexception:: ProfileNotExistsException

.. autoexception:: ProfileHasNoPicsException

.. autoexception:: PrivateProfileNotFollowedException

.. autoexception:: LoginRequiredException

.. autoexception:: InvalidArgumentException

.. autoexception:: BadResponseException

.. autoexception:: BadCredentialsException

.. autoexception:: ConnectionException
