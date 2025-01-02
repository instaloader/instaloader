Resumable Iterations
^^^^^^^^^^^^^^^^^^^^

.. module:: instaloader
   :no-index:

.. highlight:: python

.. contents::
   :backlinks: none

For many download targets, Instaloader is able to resume a
previously-interrupted iteration. It provides an interruptible
Iterator :class:`NodeIterator` and a context manager
:func:`resumable_iteration`, which we both present here.

.. versionadded:: 4.5

``NodeIterator``
""""""""""""""""

.. autoclass:: NodeIterator
   :no-show-inheritance:

.. autoclass:: FrozenNodeIterator
   :no-show-inheritance:

   A serializable representation of a :class:`NodeIterator` instance, saving
   its iteration state.

   It can be serialized and deserialized with :func:`save_structure_to_file`
   and :func:`load_structure_from_file`, as well as with :mod:`json` and
   :mod:`pickle` thanks to being a :class:`~typing.NamedTuple`.

``resumable_iteration``
"""""""""""""""""""""""

.. autofunction:: resumable_iteration