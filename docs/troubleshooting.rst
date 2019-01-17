.. _troubleshooting:

Troubleshooting
===============

.. highlight:: python

429 - Too Many Requests
-----------------------

Instaloader has a logic to keep track of its requests to Instagram and to obey
their rate limits. Since they are nowhere documented, we try them out
experimentally. We have a daily cron job running to confirm that Instaloader
still stays within the rate limits. Nevertheless, the rate control logic assumes
that

- at one time, Instaloader is the only application that consumes requests. I.e.
  neither the Instagram browser interface, nor a mobile app, nor another
  Instaloader instance is running in parallel,

- no requests had been consumed when Instaloader starts.

The latter one implies that restarting or reinstantiating Instaloader often
within short time is prone to cause a 429. When a request is denied with a 429,
Instaloader retries the request as soon as the temporary ban is assumed to be
expired. In case the retry continuously fails for some reason, which should not
happen in normal conditions, consider adjusting the
:option:`--max-connection-attempts` option.

**"Too many queries in the last time"** is not an error. It is a notice that the
rate limit has almost been reached, according to Instaloader's own rate
accounting mechanism. We regularly adjust this mechanism to match Instagram's
current rate limiting.

Login error
-----------

Instaloader's login *should* work fine, both with and without
Two-Factor-Authentication. It also supports handling the *checkpoint challenge*,
issued when Instagram suspects authentication activity on your account, by
pointing the user to an URL to be opened in a browser.

Nevertheless, in :issue:`92` users report problems with logging in. To still use
Instaloader's logged-in functionality, you may use the following script to
workaround login problems by importing the session cookies from Firefox and
bypassing Instaloader's login.

.. literalinclude:: codesnippets/92_import_firefox_session.py

To use this,

#. login to Instagram in Firefox, 

#. execute the snippet,

#. then, ``instaloader -l USERNAME`` should work fine.

If you do not use your default firefox profile, or your operating system has the
paths differently set up, you may have to alter the ``FIREFOXCOOKIEFILE``
variable first.
