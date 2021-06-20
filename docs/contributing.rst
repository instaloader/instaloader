.. _contributing:

Contributing to Instaloader
===========================

As an open source project, Instaloader heavily depends on the contributions from
its community.  In this document, we advise on how you may help Instaloader to
become an even greater tool.

Instaloader's development is organized on 
`GitHub <https://github.com/instaloader/instaloader>`__, where Issues and Pull
Requests are discussed.

Contributing to an open source project is an unmatchable opportunity to improve
and manifest programming skills. For issues that are good starting points to get
involved in Instaloader development, as they do not require deep insight into
Instaloader's code base, have a look at our
`Issues labelled 'good first issue' <https://github.com/instaloader/instaloader/contribute>`__.

This document covers several ways of how you can contribute back to Instaloader.

Answering Questions
-------------------

The easiest way to help out is to answer questions. If you are interested in
answering questions regarding Instaloader, good places to begin are

- `Questions tagged 'instaloader' on Stack Overflow <https://stackoverflow.com/questions/tagged/instaloader>`__,
- `Instaloader Issues labeled 'question' <https://github.com/instaloader/instaloader/issues?q=is%3Aissue+is%3Aopen+label%3Aquestion>`__.

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

- Even if it seems obvious, describe **which behavior you expected**
  instead of what actually happened.

- If we have closed an issue apparently inadvertently or inappropriately, please
  let us know.

Writing Code or Improving the Documentation
-------------------------------------------

Improvements of the Instaloader source or its documentation can be proposed as a
`Pull Request <https://github.com/instaloader/instaloader/pulls>`__.

- Please base your Pull Request on

  - ``master``, which will be released with the next minor release, if it is

    - a bug fix that does not require extensive testing,
    - an improvement to the documentation,

  - ``upcoming/v4.X``, if it is

    - a new feature,
    - a bug fix that does require thorough testing before being released to a
      final version.

- All Pull Requests are analyzed by `Pylint <https://www.pylint.org/>`__ for
  error and syntax checking of the source and
  `Mypy <https://github.com/python/mypy>`__ for type checking. You can run them
  locally with::

     pylint instaloader
     mypy -m instaloader

- Improvements to the documentation are very welcome. The documentation is
  created with `Sphinx <https://www.sphinx-doc.org/en/2.0/>`__, version 2,
  and can be build locally using::

     make -C docs html

- Feel free to create an issue to make sure someone from the Instaloader team
  agrees that the change might be an improvement, or if you want to discuss
  your basic proposal, before working on a pull request.

Proposing Features
------------------

.. goal-start

Instaloader's goal is to mimic the browser's behavior to access the data that
is available through the Instagram web interface, pack this data into complete
and easily-(re)usable python objects, and provide a user interface for the most
common downloading and metadata collection tasks, without changing any of the
online data.

.. goal-end

Prior spending effort on implementing a new feature, it might be appropriate to
clarify how it could fit into the project's scope or discuss implementation
details. If you feel the need to do so, please create a "feature suggestion".

- Instaloader already has plenty of features. **Check the documentation**
  beforehand to ensure your desired suggestion is not already implemented.

- Briefly **ensure that your idea has not already been suggested**. If you find
  an issue suggesting the same or a similar feature, share your thoughts in a
  comment there, instead of opening a new issue.

- **Motivate the feature**, i.e.

  - Provide us a **use case of the feature**: How could the user
    invoke the new function? Which problem would it solve? If new information is
    obtained, how would it be further processed?

  - Describe already-working **alternatives of the feature** and how they
    compare to your proposed feature.

  - Briefly describe how your suggested feature **conforms with Instaloader's
    project goal**.

- Explain your **solution ideas**. Describe your ideas on how the feature could
  be implemented and the underlying problem could be solved. Also **describe
  alternatives** that you have considered.

Sponsoring
----------

.. include:: sponsors.rst
   :start-after: donations-start
   :end-before: donations-end
