.. _contributing:

Contributing to Instaloader
===========================

As an open source project, Instaloader heavily depends on the contributions from
its community.  In this document, we advise on how you may help Instaloader to
become an even greater tool.

Instaloader's development is organized on 
`GitHub <https://github.com/instaloader/instaloader>`__, where Issues and Pull
Requests are discussed.

Reporting Bugs
--------------

If you encounter a bug, do not hesitate to report it in our
`Issue Tracker <https://github.com/instaloader/instaloader/issues>`__. When
reporting a problem, please keep the following in mind:

- Ensure you **use the latest version** of Instaloader. The currently-installed
  version can be found out with ``instaloader --version``.

- Check whether there is a valid solution in our :ref:`troubleshooting` section.

- Briefly **check whether the bug has already been reported**. If you find an
  issue reporting the same bug you encountered, comment there rather than
  opening a new issue. However, if unsure, please create a new issue.

- State **how the bug can be reproduced**, i.e. how Instaloader was invoked
  when the problem occurred (of course, you may anonymize profile names etc.).

- Include all **error messages and tracebacks** in the report.

- If not obvious, describe **which behavior you expected**
  instead of what actually happened.

- If you think an issue has been closed accidentally or inappropriately, feel
  free to reopen it.

Writing Code or Improving the Documentation
-------------------------------------------

Changes of the Instaloader source can be proposed as a
`Pull Request <https://github.com/instaloader/instaloader/pulls>`__. There are only
few things to consider:

- Sometimes, the most current code is not in the ``master`` branch. Check that
  you forked from the most recent branch.

- We use `Pylint <https://www.pylint.org/>`__ for error and syntax checking of
  the source. The file ``.travis.yml`` in the project's root directory
  shows how it is invoked. Note that sometimes it might be better to disable a
  warning rather than adapting the code to Pylint's desires.

- The documentation source is located in the ``docs`` folder. The file
  ``cli-options.rst`` is merely an RST-formatted copy of ``instaloader --help``
  output, of which the source is in ``instaloader/__main__.py``.

- Feel free to contact us, even if you "only" have Proof-of-Concepts or
  not-fully integrated changes. They already might be an advance for the
  project.

Suggesting Features
-------------------

.. goal-start

Instaloader's goal is to mimick the browser's behavior to access the data that
is available through the Instagram web interface, pack this data into complete
and easily-(re)usable python objects, and provide a user interface for the most
common downloading and metadata collection tasks, without changing any of the
online data.

.. goal-end

If you have an idea of how Instaloader should be enhanced, but do not want to
implement the feature yourself, feel free to open a ticket in our 
`Issue Tracker <https://github.com/instaloader/instaloader/issues>`__.
Please consider the following:

- Instaloader already has plenty of features. **Check the documentation**
  beforehand to ensure your desired suggestion is not already implemented.

- Briefly **ensure that your idea has not already been suggested**. If you find
  an issue suggesting the same or a similar feature, share your thoughts in a
  comment there, instead of opening a new issue.

- If possible, provide us a **use case of the feature**: How could the user
  invoke the new function? Which problem would it solve? If new information is
  obtained, how would it be further processed?

- If not obvious, briefly motivate how your suggested feature **conforms with
  Instaloader's project goal**.

- **Be patient**. Naturally, bugs and pull requests have a higher priority than
  feature suggestions. Keep in mind that this is a free software project, and
  unfortunately we only have limited time to work on it.

Donations
---------

.. donations-start

It is a pleasure for us to share our Instaloader to the world, and we are proud
to have attracted such an active and motivating community, with so many users
who share their suggestions and ideas with us. Buying a community-sponsored beer
or coffee from time to time is very likely to further raise our passion for the
development of Instaloader.

| For donations, we provide a PayPal.Me link and a Bitcoin address.
|  `PayPal.me/aandergr <https://www.paypal.me/aandergr>`__
|  BTC: 1Nst4LoadeYzrKjJ1DX9CpbLXBYE9RKLwY

.. donations-end

.. (Discussion in :issue:`130`)
