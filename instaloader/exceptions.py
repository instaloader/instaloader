class InstaloaderException(Exception):
    """Base exception for this script.

    :note: This exception should not be raised directly."""
    pass


class QueryReturnedBadRequestException(InstaloaderException):
    pass


class QueryReturnedNotFoundException(InstaloaderException):
    pass


class QueryReturnedForbiddenException(InstaloaderException):
    pass


class ProfileNotExistsException(InstaloaderException):
    pass


class ProfileHasNoPicsException(InstaloaderException):
    pass


class PrivateProfileNotFollowedException(InstaloaderException):
    pass


class LoginRequiredException(InstaloaderException):
    pass


class InvalidArgumentException(InstaloaderException):
    pass


class BadResponseException(InstaloaderException):
    pass


class BadCredentialsException(InstaloaderException):
    pass


class ConnectionException(InstaloaderException):
    pass


class TooManyRequestsException(ConnectionException):
    pass
