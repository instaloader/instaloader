"""HTTP/2 transport for Instagram requests.

Instagram has started answering HTTP/1.1 requests to its web API with ``429 Too
Many Requests`` and an empty body. It is not a rate limit: it hits the very first
request of a fresh session, and neither the session, the account nor the IP
address makes a difference. The same request over HTTP/2 succeeds, so Instaloader
has to speak HTTP/2 -- which Requests, being built on urllib3, cannot do.

This module bridges the gap with a :class:`requests.adapters.HTTPAdapter` that
hands the request over to HTTPX (which does speak HTTP/2) and converts the reply
back into a :class:`requests.Response`. Mounting the adapter keeps cookie
handling, redirects and the rest of Instaloader's Requests-based code untouched.
"""

import http.client
import io
from typing import Optional

import httpx
import requests
import requests.adapters
import urllib3

# Set by the transport itself; forwarding them to HTTPX would conflict with the
# HTTP/2 pseudo-headers or with the body HTTPX re-encodes.
_SKIPPED_REQUEST_HEADERS = frozenset({'host', 'connection', 'transfer-encoding', 'content-length'})

# HTTPX transparently decompresses the body, so passing these on would make
# urllib3 attempt to decode the payload a second time.
_SKIPPED_RESPONSE_HEADERS = frozenset({'content-encoding', 'content-length', 'transfer-encoding'})


class _OriginalResponse:
    """The bit of :mod:`http.client` API that Requests needs to extract cookies."""

    def __init__(self, headers: httpx.Headers):
        self.msg = http.client.HTTPMessage()
        for name, value in headers.multi_items():
            self.msg.add_header(name, value)

    def isclosed(self) -> bool:
        return True

    def close(self) -> None:
        pass


class HTTP2Adapter(requests.adapters.HTTPAdapter):
    """Requests transport adapter that performs the request over HTTP/2.

    .. versionadded:: 4.15.4"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._client = httpx.Client(http2=True, follow_redirects=False, timeout=None)

    def send(self, request, stream=False, timeout=None, verify=True, cert=None, proxies=None):
        headers = {name: value for name, value in request.headers.items()
                   if name.lower() not in _SKIPPED_REQUEST_HEADERS}
        try:
            response = self._client.request(
                request.method,
                request.url,
                headers=headers,
                content=request.body,
                timeout=self._httpx_timeout(timeout),
            )
        except httpx.TimeoutException as err:
            raise requests.exceptions.Timeout(err, request=request) from err
        except httpx.HTTPError as err:
            raise requests.exceptions.ConnectionError(err, request=request) from err
        return self.build_response(request, self._to_urllib3_response(response))

    def close(self) -> None:
        self._client.close()
        super().close()

    @staticmethod
    def _httpx_timeout(timeout) -> Optional[httpx.Timeout]:
        if timeout is None:
            return None
        if isinstance(timeout, tuple):
            connect, read = timeout
            return httpx.Timeout(read, connect=connect)
        return httpx.Timeout(timeout)

    @staticmethod
    def _to_urllib3_response(response: httpx.Response) -> urllib3.HTTPResponse:
        # Reading the body eagerly is fine here: the adapter only serves
        # Instagram's API hosts, whose replies are small JSON documents. Media
        # files are downloaded from the CDN, which the adapter is not mounted on.
        body = response.content
        headers = urllib3.HTTPHeaderDict()
        for name, value in response.headers.multi_items():
            if name.lower() not in _SKIPPED_RESPONSE_HEADERS:
                headers.add(name, value)
        headers['Content-Length'] = str(len(body))
        return urllib3.HTTPResponse(
            body=io.BytesIO(body),
            headers=headers,
            status=response.status_code,
            reason=response.reason_phrase,
            version=20 if response.http_version == 'HTTP/2' else 11,
            preload_content=False,
            decode_content=False,
            # urllib3 only ever touches ._original_response.msg here, which the
            # shim provides; it is not a real http.client.HTTPResponse.
            original_response=_OriginalResponse(response.headers),  # type: ignore[arg-type]
            request_method=response.request.method,
        )
