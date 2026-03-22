from functools import partial
from typing import Any, Dict, Optional, Tuple, Type

import requests
import requests.utils

try:
    from curl_cffi import requests as cffi_requests
    HAS_CURL_CFFI = True
except ImportError:
    cffi_requests = None # type: ignore
    HAS_CURL_CFFI = False

def _is_redirect_prop(self: Any) -> bool:
    return getattr(self, 'status_code', 200) in [301, 302, 303, 307, 308]

class NetworkController:
    REQUEST_EXCEPTIONS: Tuple[Type[BaseException], ...]

    def __init__(self, impersonate: Optional[str] = None):
        self.impersonate = impersonate

        if HAS_CURL_CFFI:
            self.REQUEST_EXCEPTIONS = (
                requests.exceptions.RequestException,
                cffi_requests.exceptions.RequestException # type: ignore
            )
        else:
            self.REQUEST_EXCEPTIONS = (requests.exceptions.RequestException,) # type: ignore

    def get_session(self) -> Any:
        if self.impersonate:
            if not HAS_CURL_CFFI:
                raise ImportError("curl_cffi is required for impersonate feature.")

            _impersonate = self.impersonate
            # Inherits public methods from Session; only __init__ is overridden
            class ImpersonateSession(cffi_requests.Session): # pylint: disable=too-few-public-methods
                def __init__(self, *args: Any, **kwargs: Any) -> None:
                    super().__init__(*args, **kwargs, impersonate=_impersonate) # type: ignore

            if not hasattr(cffi_requests.models.Response, 'is_redirect'):
                cffi_requests.models.Response.is_redirect = property(_is_redirect_prop) # type: ignore

            return ImpersonateSession()

        return requests.Session()

    def copy_session(self, session: Any, request_timeout: Optional[float] = None) -> Any:
        new = self.get_session()

        if self.impersonate and session.cookies.__class__.__name__ == 'Cookies':
            cookie_dict = dict(session.cookies)
        else:
            cookie_dict = requests.utils.dict_from_cookiejar(session.cookies)

        if self.impersonate and new.cookies.__class__.__name__ == 'Cookies':
            new.cookies.update(cookie_dict)
        else:
            # False positives: setting attributes on the new session object, not on self
            new.cookies = requests.utils.cookiejar_from_dict(cookie_dict) # pylint: disable=attribute-defined-outside-init

        new.headers = session.headers.copy() # pylint: disable=attribute-defined-outside-init
        new.request = partial(new.request, timeout=request_timeout) # pylint: disable=attribute-defined-outside-init
        return new

    def dict_from_cookiejar(self, cookies: Any) -> Dict[str, str]:
        if hasattr(cookies, 'get_dict'):
            return cookies.get_dict() # type: ignore
        return requests.utils.dict_from_cookiejar(cookies)

    def cookiejar_from_dict(self, cookie_dict: Dict[str, str]) -> Any:
        if self.impersonate and HAS_CURL_CFFI:
            from curl_cffi.requests.cookies import Cookies # type: ignore # pylint: disable=import-outside-toplevel
            c = Cookies()
            c.update(cookie_dict)
            return c
        return requests.utils.cookiejar_from_dict(cookie_dict)

if HAS_CURL_CFFI:
    REQUEST_EXCEPTIONS = (
        requests.exceptions.RequestException,
        cffi_requests.exceptions.RequestException # type: ignore
    )
else:
    REQUEST_EXCEPTIONS = (requests.exceptions.RequestException,) # type: ignore
