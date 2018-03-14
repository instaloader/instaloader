.. image:: https://raw.githubusercontent.com/instaloader/instaloader/master/docs/logo_heading.png

::

    $ pip3 install instaloader

    $ instaloader profile [profile ...]

**Instaloader**

- downloads **public and private profiles, hashtags, user stories,
  feeds and saved media**,

- downloads **comments, geotags and captions** of each post,

- automatically **detects profile name changes** and renames the target
  directory accordingly,

- allows **fine-grained customization** of filters and where to store
  downloaded media.

::

    instaloader [--comments] [--geotags] [--stories]
                [--login YOUR-USERNAME] [--fast-update]
                profile | "#hashtag" | :stories | :feed | :saved

`Instaloader Documentation <https://instaloader.github.io/>`__


How to Automatically Download Pictures from Instagram
-----------------------------------------------------

To **download all pictures and videos of a profile**, as well as the
**profile picture**, do

::

    instaloader profile [profile ...]

where ``profile`` is the name of a profile you want to download. Instead
of only one profile, you may also specify a list of profiles.

To later **update your local copy** of that profiles, you may run

::

    instaloader --fast-update profile [profile ...]

If ``--fast-update`` is given, Instaloader stops when arriving at the
first already-downloaded picture. When updating profiles, Instaloader
automatically **detects profile name changes** and renames the target directory
accordingly.

Instaloader can also be used to **download private profiles**. To do so,
invoke it with

::

    instaloader --login=your_username profile [profile ...]

When logging in, Instaloader **stores the session cookies** in a file in your
temporary directory, which will be reused later the next time ``--login``
is given.  So you can download private profiles **non-interactively** when you
already have a valid session cookie file.

`Instaloader Documentation <https://instaloader.github.io/basic-usage.html>`__


Disclaimer
----------

.. disclaimer-start

Instaloader is in no way affiliated with, authorized, maintained or endorsed by Instagram or any of its affiliates or
subsidiaries. This is an independent and unofficial project. Use at your own risk.

.. disclaimer-end

Instaloader is licensed under an MIT license. Refer to ``LICENSE`` file for more information.
