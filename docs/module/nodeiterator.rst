Resumable Iterations
^^^^^^^^^^^^^^^^^^^^

.. module:: instaloader
   :noindex:

.. highlight:: python

.. contents::
   :backlinks: none

For many download targets, Instaloader is able to resume a
previously-interrupted iteration. It provides an interruptable
Iterator :class:`NodeIterator` and a context manager
:func:`resumable_iteration`, which we both present here.

.. versionadded:: 4.5

``NodeIterator``
""""""""""""""""

.. autoclass:: NodeIterator
   :no-show-inheritance:

.. autoclass:: FrozenNodeIterator
   :no-show-inheritance:

``resumable_iteration``
"""""""""""""""""""""""

.. autofunction:: resumable_iteration