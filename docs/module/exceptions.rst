Exceptions
^^^^^^^^^^

.. module:: instaloader
   :no-index:

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

.. autoexception:: LoginException

   .. versionadded:: 4.12

.. autoexception:: TwoFactorAuthRequiredException

   .. versionadded:: 4.2

   .. versionchanged:: 4.12
      Inherits LoginException

.. autoexception:: InvalidArgumentException

.. autoexception:: BadResponseException

.. autoexception:: BadCredentialsException

   .. versionchanged:: 4.12
      Inherits LoginException

.. autoexception:: PostChangedException

.. autoexception:: QueryReturnedNotFoundException

   .. versionchanged:: 4.3
      QueryReturnedNotFoundException now inherits ConnectionException
      to retry on 404 errors.


.. autoexception:: TooManyRequestsException

.. autoexception:: AbortDownloadException
