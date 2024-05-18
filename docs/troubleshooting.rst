.. _troubleshooting:

Troubleshooting
===============

.. highlight:: python

429 Too Many Requests
---------------------

Instaloader has a logic to keep track of its requests to Instagram and to obey
their rate limits. The rate controller assumes that

- at one time, Instaloader is the only application that consumes requests, i.e.
  neither the Instagram browser interface, nor a mobile app, nor another
  Instaloader instance is running in parallel, and

- no requests had been consumed when Instaloader starts.

The latter one implies that restarting or reinstantiating Instaloader often
within short time is prone to cause a 429.

Since the behavior of the rate controller might change between different
versions of Instaloader, make sure to use the current version of Instaloader,
especially when encountering many 429 errors.

If a request is denied with a 429,
Instaloader retries the request as soon as the temporary ban is assumed to be
expired. In case the retry continuously fails for some reason, which should not
happen under normal conditions, consider adjusting the
:option:`--max-connection-attempts` option.

There have been observations that services, that in their nature offer
promiscuous IP addresses, such as cloud, VPN and public proxy services, might be
subject to significantly stricter limits for anonymous access. However,
:ref:`logged-in accesses<login>` do not seem to be affected.

Instaloader allows to adjust the rate controlling behavior by overriding
:class:`instaloader.RateController`.

Too many queries in the last time
---------------------------------

**"Too many queries in the last time"** is not an error. It is a notice that the
rate limit has almost been reached, according to Instaloader's own rate
accounting mechanism.

Instaloader allows to adjust the rate controlling behavior by overriding
:class:`instaloader.RateController`.

Private but not followed
------------------------

You have to follow a private account to access most of its associated
information.

Login error
-----------

Instaloader's login *should* work fine, both with and without
Two-Factor-Authentication. It also supports handling the *checkpoint challenge*,
issued when Instagram suspects authentication activity on your account, by
pointing the user to an URL to be opened in a browser.

Nevertheless, in :issue:`92`, :issue:`615`, :issue:`1150` and :issue:`1217`,
users reported problems with
logging in. We recommend to always keep the session file which Instaloader
creates when using :option:`--login`. If a session file is present,
:option:`--login` does not make use of the failure-prone login procedure.
Also, session files usually do not expire.

If you do not have a session file present, you may use the following script
(:example:`615_import_firefox_session.py`) to workaround login problems by
importing the session cookies from Firefox and bypassing Instaloader's login and
so still use Instaloader's logged-in functionality.

.. literalinclude:: codesnippets/615_import_firefox_session.py

To use this script,

#. Download the script: :example:`615_import_firefox_session.py`,

#. Login to Instagram in Firefox,

#. Execute the snippet, e.g. with ``python 615_import_firefox_session.py``,

#. Then, ``instaloader -l USERNAME`` should work fine.

This script also supports specifying a cookie file path, which may be useful if
you use multiple Firefox profiles or if your operating system has the directory
structure differently set up. Also, you can specify an alternative session file
path.
