Exceptions
^^^^^^^^^^

.. module:: instaloader
   :noindex:

.. highlight:: python

.. currentmodule:: instaloader.exceptions

.. autoexception:: InstaloaderException
   :no-show-inheritance:

.. autoexception:: ConnectionException

.. currentmodule:: instaloader

.. autoexception:: QueryReturnedBadRequestException

.. autoexception:: QueryReturnedForbiddenException

.. autoexception:: ProfileNotExistsException

.. autoexception:: ProfileHasNoPicsException

.. autoexception:: PrivateProfileNotFollowedException

.. autoexception:: LoginRequiredException

.. autoexception:: TwoFactorAuthRequiredException

   .. versionadded:: 4.2

.. autoexception:: InvalidArgumentException

.. autoexception:: BadResponseException

.. autoexception:: BadCredentialsException

.. autoexception:: PostChangedException

.. autoexception:: QueryReturnedNotFoundException

   .. versionchanged:: 4.3
      QueryReturnedNotFoundException now inherits ConnectionException
      to retry on 404 errors.


.. autoexception:: TooManyRequestsException

.. autoexception:: AbortDownloadException
