import hashlib
import json
import os
import pickle
import random
import shutil
import sys
import textwrap
import time
import urllib.parse
import uuid
from contextlib import contextmanager, suppress
from datetime import datetime, timedelta
from functools import partial
from typing import Any, Callable, Dict, Iterator, List, Optional, Union

import requests
import requests.utils

from .exceptions import *


def copy_session(session: requests.Session, request_timeout: Optional[float] = None) -> requests.Session:
    """Duplicates a requests.Session."""
    new = requests.Session()
    new.cookies = requests.utils.cookiejar_from_dict(requests.utils.dict_from_cookiejar(session.cookies))
    new.headers = session.headers.copy()  # type: ignore
    # Override default timeout behavior.
    # Need to silence mypy bug for this. See: https://github.com/python/mypy/issues/2427
    new.request = partial(new.request, timeout=request_timeout)  # type: ignore
    return new


def default_user_agent() -> str:
    return ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')


def default_iphone_headers() -> Dict[str, Any]:
    return {'User-Agent': 'Instagram 273.0.0.16.70 (iPad13,8; iOS 16_3; en_US; en-US; ' \
                          'scale=2.00; 2048x2732; 452417278) AppleWebKit/420+',
            'x-ads-opt-out': '1',
            'x-bloks-is-panorama-enabled': 'true',
            'x-bloks-version-id': '01507c21540f73e2216b6f62a11a5b5e51aa85491b72475c080da35b1228ddd6',
            'x-fb-client-ip': 'True',
            'x-fb-connection-type': 'wifi',
            'x-fb-http-engine': 'Liger',
            'x-fb-server-cluster': 'True',
            'x-fb': '1',
            'x-ig-abr-connection-speed-kbps': '2',
            'x-ig-app-id': '124024574287414',
            'x-ig-app-locale': 'en-US',
            'x-ig-app-startup-country': 'US',
            'x-ig-bandwidth-speed-kbps': '0.000',
            'x-ig-capabilities': '36r/F/8=',
            'x-ig-connection-speed': '{}kbps'.format(random.randint(1000, 20000)),
            'x-ig-connection-type': 'WiFi',
            'x-ig-device-locale': 'en-US',
            'x-ig-mapped-locale': 'en-US',
            'x-ig-timezone-offset': str((datetime.now().astimezone().utcoffset() or timedelta(seconds=0)).seconds),
            'x-ig-www-claim': '0',
            'x-pigeon-session-id': str(uuid.uuid4()),
            'x-tigon-is-retry': 'False',
            'x-whatsapp': '0'}


class InstaloaderContext:
    """Class providing methods for (error) logging and low-level communication with Instagram.

    It is not thought to be instantiated directly, rather :class:`Instaloader` instances maintain a context
    object.

    For logging, it provides :meth:`log`, :meth:`error`, :meth:`error_catcher`.

    It provides low-level communication routines :meth:`get_json`, :meth:`graphql_query`, :meth:`graphql_node_list`,
    :meth:`get_and_write_raw` and implements mechanisms for rate controlling and error handling.

    Further, it provides methods for logging in and general session handles, which are used by that routines in
    class :class:`Instaloader`.
    """

    def __init__(self, sleep: bool = True, quiet: bool = False, user_agent: Optional[str] = None,
                 max_connection_attempts: int = 3, request_timeout: float = 300.0,
                 rate_controller: Optional[Callable[["InstaloaderContext"], "RateController"]] = None,
                 fatal_status_codes: Optional[List[int]] = None,
                 iphone_support: bool = True):

        self.user_agent = user_agent if user_agent is not None else default_user_agent()
        self.request_timeout = request_timeout
        self._session = self.get_anonymous_session()
        self.username = None
        self.user_id = None
        self.sleep = sleep
        self.quiet = quiet
        self.max_connection_attempts = max_connection_attempts
        self._graphql_page_length = 50
        self._root_rhx_gis = None
        self.two_factor_auth_pending = None
        self.iphone_support = iphone_support
        self.iphone_headers = default_iphone_headers()

        # error log, filled with error() and printed at the end of Instaloader.main()
        self.error_log: List[str] = []

        self._rate_controller = rate_controller(self) if rate_controller is not None else RateController(self)

        # Can be set to True for testing, disables supression of InstaloaderContext._error_catcher
        self.raise_all_errors = False

        # HTTP status codes that should cause an AbortDownloadException
        self.fatal_status_codes = fatal_status_codes or []

        # Cache profile from id (mapping from id to Profile)
        self.profile_id_cache: Dict[int, Any] = dict()

    @contextmanager
    def anonymous_copy(self):
        session = self._session
        username = self.username
        user_id = self.user_id
        iphone_headers = self.iphone_headers
        self._session = self.get_anonymous_session()
        self.username = None
        self.user_id = None
        self.iphone_headers = default_iphone_headers()
        try:
            yield self
        finally:
            self._session.close()
            self.username = username
            self._session = session
            self.user_id = user_id
            self.iphone_headers = iphone_headers

    @property
    def is_logged_in(self) -> bool:
        """True, if this Instaloader instance is logged in."""
        return bool(self.username)

    def log(self, *msg, sep='', end='\n', flush=False):
        """Log a message to stdout that can be suppressed with --quiet."""
        if not self.quiet:
            print(*msg, sep=sep, end=end, flush=flush)

    def error(self, msg, repeat_at_end=True):
        """Log a non-fatal error message to stderr, which is repeated at program termination.

        :param msg: Message to be printed.
        :param repeat_at_end: Set to false if the message should be printed, but not repeated at program termination."""
        print(msg, file=sys.stderr)
        if repeat_at_end:
            self.error_log.append(msg)

    @property
    def has_stored_errors(self) -> bool:
        """Returns whether any error has been reported and stored to be repeated at program termination.

        .. versionadded: 4.12"""
        return bool(self.error_log)

    def close(self):
        """Print error log and close session"""
        if self.error_log and not self.quiet:
            print("\nErrors or warnings occurred:", file=sys.stderr)
            for err in self.error_log:
                print(err, file=sys.stderr)
        self._session.close()

    @contextmanager
    def error_catcher(self, extra_info: Optional[str] = None):
        """
        Context manager to catch, print and record InstaloaderExceptions.

        :param extra_info: String to prefix error message with."""
        try:
            yield
        except InstaloaderException as err:
            if extra_info:
                self.error('{}: {}'.format(extra_info, err))
            else:
                self.error('{}'.format(err))
            if self.raise_all_errors:
                raise

    def _default_http_header(self, empty_session_only: bool = False) -> Dict[str, str]:
        """Returns default HTTP header we use for requests."""
        header = {'Accept-Encoding': 'gzip, deflate',
                  'Accept-Language': 'en-US,en;q=0.8',
                  'Connection': 'keep-alive',
                  'Content-Length': '0',
                  'Host': 'www.instagram.com',
                  'Origin': 'https://www.instagram.com',
                  'Referer': 'https://www.instagram.com/',
                  'User-Agent': self.user_agent,
                  'X-Instagram-AJAX': '1',
                  'X-Requested-With': 'XMLHttpRequest'}
        if empty_session_only:
            del header['Host']
            del header['Origin']
            del header['X-Instagram-AJAX']
            del header['X-Requested-With']
        return header

    def get_anonymous_session(self) -> requests.Session:
        """Returns our default anonymous requests.Session object."""
        session = requests.Session()
        session.cookies.update({'sessionid': '', 'mid': '', 'ig_pr': '1',
                                'ig_vw': '1920', 'csrftoken': '',
                                's_network': '', 'ds_user_id': ''})
        session.headers.update(self._default_http_header(empty_session_only=True))
        # Override default timeout behavior.
        # Need to silence mypy bug for this. See: https://github.com/python/mypy/issues/2427
        session.request = partial(session.request, timeout=self.request_timeout) # type: ignore
        return session

    def save_session(self):
        """Not meant to be used directly, use :meth:`Instaloader.save_session`."""
        return requests.utils.dict_from_cookiejar(self._session.cookies)

    def update_cookies(self, cookie):
        """.. versionadded:: 4.11"""
        self._session.cookies.update(cookie)

    def load_session(self, username, sessiondata):
        """Not meant to be used directly, use :meth:`Instaloader.load_session`."""
        session = requests.Session()
        session.cookies = requests.utils.cookiejar_from_dict(sessiondata)
        session.headers.update(self._default_http_header())
        session.headers.update({'X-CSRFToken': session.cookies.get_dict()['csrftoken']})
        # Override default timeout behavior.
        # Need to silence mypy bug for this. See: https://github.com/python/mypy/issues/2427
        session.request = partial(session.request, timeout=self.request_timeout)  # type: ignore
        self._session = session
        self.username = username

    def save_session_to_file(self, sessionfile):
        """Not meant to be used directly, use :meth:`Instaloader.save_session_to_file`."""
        pickle.dump(self.save_session(), sessionfile)

    def load_session_from_file(self, username, sessionfile):
        """Not meant to be used directly, use :meth:`Instaloader.load_session_from_file`."""
        self.load_session(username, pickle.load(sessionfile))

    def test_login(self) -> Optional[str]:
        """Not meant to be used directly, use :meth:`Instaloader.test_login`."""
        try:
            data = self.graphql_query("d6f4427fbe92d846298cf93df0b937d3", {})
            return data["data"]["user"]["username"] if data["data"]["user"] is not None else None
        except (AbortDownloadException, ConnectionException) as err:
            self.error(f"Error when checking if logged in: {err}")
            return None

    def login(self, user, passwd):
        """Not meant to be used directly, use :meth:`Instaloader.login`.

        :raises BadCredentialsException: If the provided password is wrong.
        :raises TwoFactorAuthRequiredException: First step of 2FA login done, now call
           :meth:`Instaloader.two_factor_login`.
        :raises LoginException: An error happened during login (for example, and invalid response).
           Or if the provided username does not exist.

        .. versionchanged:: 4.12
           Raises LoginException instead of ConnectionException when an error happens.
           Raises LoginException instead of InvalidArgumentException when the username does not exist.
        """
        # pylint:disable=import-outside-toplevel
        import http.client
        # pylint:disable=protected-access
        http.client._MAXHEADERS = 200
        session = requests.Session()
        session.cookies.update({'sessionid': '', 'mid': '', 'ig_pr': '1',
                                'ig_vw': '1920', 'ig_cb': '1', 'csrftoken': '',
                                's_network': '', 'ds_user_id': ''})
        session.headers.update(self._default_http_header())
        # Override default timeout behavior.
        # Need to silence mypy bug for this. See: https://github.com/python/mypy/issues/2427
        session.request = partial(session.request, timeout=self.request_timeout) # type: ignore

        # Make a request to Instagram's root URL, which will set the session's csrftoken cookie
        # Not using self.get_json() here, because we need to access the cookie
        session.get('https://www.instagram.com/')
        # Add session's csrftoken cookie to session headers
        csrf_token = session.cookies.get_dict()['csrftoken']
        session.headers.update({'X-CSRFToken': csrf_token})

        self.do_sleep()
        # Workaround credits to pgrimaud.
        # See: https://github.com/pgrimaud/instagram-user-feed/commit/96ad4cf54d1ad331b337f325c73e664999a6d066
        enc_password = '#PWD_INSTAGRAM_BROWSER:0:{}:{}'.format(int(datetime.now().timestamp()), passwd)
        login = session.post('https://www.instagram.com/api/v1/web/accounts/login/ajax/',
                             data={'enc_password': enc_password, 'username': user}, allow_redirects=True)
        try:
            resp_json = login.json()

        except json.decoder.JSONDecodeError as err:
            raise LoginException(
                "Login error: JSON decode fail, {} - {}.".format(login.status_code, login.reason)
            ) from err
        if resp_json.get('two_factor_required'):
            two_factor_session = copy_session(session, self.request_timeout)
            two_factor_session.headers.update({'X-CSRFToken': csrf_token})
            two_factor_session.cookies.update({'csrftoken': csrf_token})
            self.two_factor_auth_pending = (two_factor_session,
                                            user,
                                            resp_json['two_factor_info']['two_factor_identifier'])
            raise TwoFactorAuthRequiredException("Login error: two-factor authentication required.")
        if resp_json.get('checkpoint_url'):
            raise LoginException(
                f"Login: Checkpoint required. Point your browser to {resp_json.get('checkpoint_url')} - "
                f"follow the instructions, then retry."
            )
        if resp_json['status'] != 'ok':
            if 'message' in resp_json:
                raise LoginException("Login error: \"{}\" status, message \"{}\".".format(resp_json['status'],
                                                                                          resp_json['message']))
            else:
                raise LoginException("Login error: \"{}\" status.".format(resp_json['status']))
        if 'authenticated' not in resp_json:
            # Issue #472
            if 'message' in resp_json:
                raise LoginException("Login error: Unexpected response, \"{}\".".format(resp_json['message']))
            else:
                raise LoginException("Login error: Unexpected response, this might indicate a blocked IP.")
        if not resp_json['authenticated']:
            if resp_json['user']:
                # '{"authenticated": false, "user": true, "status": "ok"}'
                raise BadCredentialsException('Login error: Wrong password.')
            else:
                # '{"authenticated": false, "user": false, "status": "ok"}'
                # Raise LoginException rather than BadCredentialException, because BadCredentialException
                # triggers re-asking of password in Instaloader.interactive_login(), which makes no sense if the
                # username is invalid.
                raise LoginException('Login error: User {} does not exist.'.format(user))
        # '{"authenticated": true, "user": true, "userId": ..., "oneTapPrompt": false, "status": "ok"}'
        session.headers.update({'X-CSRFToken': login.cookies['csrftoken']})
        self._session = session
        self.username = user
        self.user_id = resp_json['userId']

    def two_factor_login(self, two_factor_code):
        """Second step of login if 2FA is enabled.
        Not meant to be used directly, use :meth:`Instaloader.two_factor_login`.

        :raises InvalidArgumentException: No two-factor authentication pending.
        :raises BadCredentialsException: 2FA verification code invalid.

        .. versionadded:: 4.2"""
        if not self.two_factor_auth_pending:
            raise InvalidArgumentException("No two-factor authentication pending.")
        (session, user, two_factor_id) = self.two_factor_auth_pending

        login = session.post('https://www.instagram.com/accounts/login/ajax/two_factor/',
                             data={'username': user, 'verificationCode': two_factor_code, 'identifier': two_factor_id},
                             allow_redirects=True)
        resp_json = login.json()
        if resp_json['status'] != 'ok':
            if 'message' in resp_json:
                raise BadCredentialsException("2FA error: {}".format(resp_json['message']))
            else:
                raise BadCredentialsException("2FA error: \"{}\" status.".format(resp_json['status']))
        session.headers.update({'X-CSRFToken': login.cookies['csrftoken']})
        self._session = session
        self.username = user
        self.two_factor_auth_pending = None

    def do_sleep(self):
        """Sleep a short time if self.sleep is set. Called before each request to instagram.com."""
        if self.sleep:
            time.sleep(min(random.expovariate(0.6), 15.0))

    @staticmethod
    def _response_error(resp: requests.Response) -> str:
        extra_from_json: Optional[str] = None
        with suppress(json.decoder.JSONDecodeError):
            resp_json = resp.json()
            if "status" in resp_json:
                extra_from_json = (
                    f"\"{resp_json['status']}\" status, message \"{resp_json['message']}\""
                    if "message" in resp_json
                    else f"\"{resp_json['status']}\" status"
                )
        return (
            f"{resp.status_code} {resp.reason}"
            f"{f' - {extra_from_json}' if extra_from_json is not None else ''}"
            f" when accessing {resp.url}"
        )

    def get_json(self, path: str, params: Dict[str, Any], host: str = 'www.instagram.com',
                 session: Optional[requests.Session] = None, _attempt=1,
                 response_headers: Optional[Dict[str, Any]] = None,
                 use_post: bool = False) -> Dict[str, Any]:
        """JSON request to Instagram.

        :param path: URL, relative to the given domain which defaults to www.instagram.com/
        :param params: request parameters
        :param host: Domain part of the URL from where to download the requested JSON; defaults to www.instagram.com
        :param session: Session to use, or None to use self.session
        :param use_post: Use POST instead of GET to make the request
        :return: Decoded response dictionary
        :raises QueryReturnedBadRequestException: When the server responds with a 400.
        :raises QueryReturnedNotFoundException: When the server responds with a 404.
        :raises ConnectionException: When query repeatedly failed.

        .. versionchanged:: 4.13
           Added `use_post` parameter.
        """
        is_graphql_query = 'query_hash' in params and 'graphql/query' in path
        is_doc_id_query = 'doc_id' in params and 'graphql/query' in path
        is_iphone_query = host == 'i.instagram.com'
        is_other_query = not is_graphql_query and not is_doc_id_query and host == "www.instagram.com"
        sess = session if session else self._session
        try:
            self.do_sleep()
            if is_graphql_query:
                self._rate_controller.wait_before_query(params['query_hash'])
            if is_doc_id_query:
                self._rate_controller.wait_before_query(params['doc_id'])
            if is_iphone_query:
                self._rate_controller.wait_before_query('iphone')
            if is_other_query:
                self._rate_controller.wait_before_query('other')
            if use_post:
                resp = sess.post('https://{0}/{1}'.format(host, path), data=params, allow_redirects=False)
            else:
                resp = sess.get('https://{0}/{1}'.format(host, path), params=params, allow_redirects=False)
            if resp.status_code in self.fatal_status_codes:
                redirect = " redirect to {}".format(resp.headers['location']) if 'location' in resp.headers else ""
                body = ""
                if resp.headers['Content-Type'].startswith('application/json'):
                    body = ': ' + resp.text[:500] + ('…' if len(resp.text) > 501 else '')
                raise AbortDownloadException("Query to https://{}/{} responded with \"{} {}\"{}{}".format(
                    host, path, resp.status_code, resp.reason, redirect, body
                ))
            while resp.is_redirect:
                redirect_url = resp.headers['location']
                self.log('\nHTTP redirect from https://{0}/{1} to {2}'.format(host, path, redirect_url))
                if (redirect_url.startswith('https://www.instagram.com/accounts/login') or
                    redirect_url.startswith('https://i.instagram.com/accounts/login')):
                    if not self.is_logged_in:
                        raise LoginRequiredException("Redirected to login page. Use --login or --load-cookies.")
                    raise AbortDownloadException("Redirected to login page. You've been logged out, please wait " +
                                                 "some time, recreate the session and try again")
                if redirect_url.startswith('https://{}/'.format(host)):
                    resp = sess.get(redirect_url if redirect_url.endswith('/') else redirect_url + '/',
                                    params=params, allow_redirects=False)
                else:
                    break
            if response_headers is not None:
                response_headers.clear()
                response_headers.update(resp.headers)
            if resp.status_code == 400:
                raise QueryReturnedBadRequestException(self._response_error(resp))
            if resp.status_code == 404:
                raise QueryReturnedNotFoundException(self._response_error(resp))
            if resp.status_code == 429:
                raise TooManyRequestsException(self._response_error(resp))
            if resp.status_code != 200:
                raise ConnectionException(self._response_error(resp))
            else:
                resp_json = resp.json()
            if 'status' in resp_json and resp_json['status'] != "ok":
                raise ConnectionException(self._response_error(resp))
            return resp_json
        except (ConnectionException, json.decoder.JSONDecodeError, requests.exceptions.RequestException) as err:
            error_string = "JSON Query to {}: {}".format(path, err)
            if _attempt == self.max_connection_attempts:
                if isinstance(err, QueryReturnedNotFoundException):
                    raise QueryReturnedNotFoundException(error_string) from err
                else:
                    raise ConnectionException(error_string) from err
            self.error(error_string + " [retrying; skip with ^C]", repeat_at_end=False)
            try:
                if isinstance(err, TooManyRequestsException):
                    if is_graphql_query:
                        self._rate_controller.handle_429(params['query_hash'])
                    if is_doc_id_query:
                        self._rate_controller.handle_429(params['doc_id'])
                    if is_iphone_query:
                        self._rate_controller.handle_429('iphone')
                    if is_other_query:
                        self._rate_controller.handle_429('other')
                return self.get_json(path=path, params=params, host=host, session=sess, _attempt=_attempt + 1,
                                     response_headers=response_headers)
            except KeyboardInterrupt:
                self.error("[skipped by user]", repeat_at_end=False)
                raise ConnectionException(error_string) from err

    def graphql_query(self, query_hash: str, variables: Dict[str, Any],
                      referer: Optional[str] = None, rhx_gis: Optional[str] = None) -> Dict[str, Any]:
        """
        Do a GraphQL Query.

        :param query_hash: Query identifying hash.
        :param variables: Variables for the Query.
        :param referer: HTTP Referer, or None.
        :param rhx_gis: 'rhx_gis' variable as somewhere returned by Instagram, needed to 'sign' request
        :return: The server's response dictionary.
        """
        with copy_session(self._session, self.request_timeout) as tmpsession:
            tmpsession.headers.update(self._default_http_header(empty_session_only=True))
            del tmpsession.headers['Connection']
            del tmpsession.headers['Content-Length']
            tmpsession.headers['authority'] = 'www.instagram.com'
            tmpsession.headers['scheme'] = 'https'
            tmpsession.headers['accept'] = '*/*'
            if referer is not None:
                tmpsession.headers['referer'] = urllib.parse.quote(referer)

            variables_json = json.dumps(variables, separators=(',', ':'))

            if rhx_gis:
                #self.log("rhx_gis {} query_hash {}".format(rhx_gis, query_hash))
                values = "{}:{}".format(rhx_gis, variables_json)
                x_instagram_gis = hashlib.md5(values.encode()).hexdigest()
                tmpsession.headers['x-instagram-gis'] = x_instagram_gis

            resp_json = self.get_json('graphql/query',
                                      params={'query_hash': query_hash,
                                              'variables': variables_json},
                                      session=tmpsession)
        if 'status' not in resp_json:
            self.error("GraphQL response did not contain a \"status\" field.")
        return resp_json

    def doc_id_graphql_query(self, doc_id: str, variables: Dict[str, Any],
                             referer: Optional[str] = None) -> Dict[str, Any]:
        """
        Do a doc_id-based GraphQL Query using method POST.

        .. versionadded:: 4.13

        :param doc_id: doc_id for the query.
        :param variables: Variables for the Query.
        :param referer: HTTP Referer, or None.
        :return: The server's response dictionary.
        """
        with copy_session(self._session, self.request_timeout) as tmpsession:
            tmpsession.headers.update(self._default_http_header(empty_session_only=True))
            del tmpsession.headers['Connection']
            del tmpsession.headers['Content-Length']
            tmpsession.headers['authority'] = 'www.instagram.com'
            tmpsession.headers['scheme'] = 'https'
            tmpsession.headers['accept'] = '*/*'
            if referer is not None:
                tmpsession.headers['referer'] = urllib.parse.quote(referer)

            variables_json = json.dumps(variables, separators=(',', ':'))

            resp_json = self.get_json('graphql/query',
                                      params={'variables': variables_json,
                                              'doc_id': doc_id,
                                              'server_timestamps': 'true'},
                                      session=tmpsession,
                                      use_post=True)
        if 'status' not in resp_json:
            self.error("GraphQL response did not contain a \"status\" field.")
        return resp_json

    def graphql_node_list(self, query_hash: str, query_variables: Dict[str, Any],
                          query_referer: Optional[str],
                          edge_extractor: Callable[[Dict[str, Any]], Dict[str, Any]],
                          rhx_gis: Optional[str] = None,
                          first_data: Optional[Dict[str, Any]] = None) -> Iterator[Dict[str, Any]]:
        """
        Retrieve a list of GraphQL nodes.

        .. deprecated:: 4.5
           Use :class:`NodeIterator` instead, which provides more functionality.
        """

        def _query():
            query_variables['first'] = self._graphql_page_length
            try:
                return edge_extractor(self.graphql_query(query_hash, query_variables, query_referer, rhx_gis))
            except QueryReturnedBadRequestException:
                new_page_length = int(self._graphql_page_length / 2)
                if new_page_length >= 12:
                    self._graphql_page_length = new_page_length
                    self.error("HTTP Error 400 (Bad Request) on GraphQL Query. Retrying with shorter page length.",
                               repeat_at_end=False)
                    return _query()
                else:
                    raise

        if first_data:
            data = first_data
        else:
            data = _query()
        yield from (edge['node'] for edge in data['edges'])
        while data['page_info']['has_next_page']:
            query_variables['after'] = data['page_info']['end_cursor']
            data = _query()
            yield from (edge['node'] for edge in data['edges'])

    def get_iphone_json(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """JSON request to ``i.instagram.com``.

        :param path: URL, relative to ``i.instagram.com/``
        :param params: GET parameters
        :return: Decoded response dictionary
        :raises QueryReturnedBadRequestException: When the server responds with a 400.
        :raises QueryReturnedNotFoundException: When the server responds with a 404.
        :raises ConnectionException: When query repeatedly failed.

        .. versionadded:: 4.2.1"""
        with copy_session(self._session, self.request_timeout) as tempsession:
            # Set headers to simulate an API request from iPad
            tempsession.headers['ig-intended-user-id'] = str(self.user_id)
            tempsession.headers['x-pigeon-rawclienttime'] = '{:.6f}'.format(time.time())

            # Add headers obtained from previous iPad request
            tempsession.headers.update(self.iphone_headers)

            # Extract key information from cookies if we haven't got it already from a previous request
            header_cookies_mapping = {'x-mid': 'mid',
                                     'ig-u-ds-user-id': 'ds_user_id',
                                     'x-ig-device-id': 'ig_did',
                                     'x-ig-family-device-id': 'ig_did',
                                     'family_device_id': 'ig_did'}

            # Map the cookie value to the matching HTTP request header
            cookies = tempsession.cookies.get_dict().copy()
            for key, value in header_cookies_mapping.items():
                if value in cookies:
                    if key not in tempsession.headers:
                        tempsession.headers[key] = cookies[value]
                    else:
                        # Remove the cookie value if it's already specified as a header
                        tempsession.cookies.pop(value, None)

            # Edge case for ig-u-rur header due to special string encoding in cookie
            if 'rur' in cookies:
                if 'ig-u-rur' not in tempsession.headers:
                    tempsession.headers['ig-u-rur'] = cookies['rur'].strip('\"').encode('utf-8') \
                                                                    .decode('unicode_escape')
                else:
                    tempsession.cookies.pop('rur', None)

            # Remove headers specific to Desktop version
            for header in ['Host', 'Origin', 'X-Instagram-AJAX', 'X-Requested-With', 'Referer']:
                tempsession.headers.pop(header, None)

            # No need for cookies if we have a bearer token
            if 'authorization' in tempsession.headers:
                tempsession.cookies.clear()

            response_headers = dict()    # type: Dict[str, Any]
            response = self.get_json(path, params, 'i.instagram.com', tempsession, response_headers=response_headers)

            # Extract the ig-set-* headers and use them in the next request
            for key, value in response_headers.items():
                if key.startswith('ig-set-'):
                    self.iphone_headers[key.replace('ig-set-', '')] = value
                elif key.startswith('x-ig-set-'):
                    self.iphone_headers[key.replace('x-ig-set-', 'x-ig-')] = value

            return response

    def write_raw(self, resp: Union[bytes, requests.Response], filename: str) -> None:
        """Write raw response data into a file.

        .. versionadded:: 4.2.1"""
        self.log(filename, end=' ', flush=True)
        with open(filename + '.temp', 'wb') as file:
            if isinstance(resp, requests.Response):
                shutil.copyfileobj(resp.raw, file)
            else:
                file.write(resp)
        os.replace(filename + '.temp', filename)

    def get_raw(self, url: str, _attempt=1) -> requests.Response:
        """Downloads a file anonymously.

        :raises QueryReturnedNotFoundException: When the server responds with a 404.
        :raises QueryReturnedForbiddenException: When the server responds with a 403.
        :raises ConnectionException: When download failed.

        .. versionadded:: 4.2.1"""
        with self.get_anonymous_session() as anonymous_session:
            resp = anonymous_session.get(url, stream=True)
        if resp.status_code == 200:
            resp.raw.decode_content = True
            return resp
        else:
            if resp.status_code == 403:
                # suspected invalid URL signature
                raise QueryReturnedForbiddenException(self._response_error(resp))
            if resp.status_code == 404:
                # 404 not worth retrying.
                raise QueryReturnedNotFoundException(self._response_error(resp))
            raise ConnectionException(self._response_error(resp))

    def get_and_write_raw(self, url: str, filename: str) -> None:
        """Downloads and writes anonymously-requested raw data into a file.

        :raises QueryReturnedNotFoundException: When the server responds with a 404.
        :raises QueryReturnedForbiddenException: When the server responds with a 403.
        :raises ConnectionException: When download repeatedly failed."""
        self.write_raw(self.get_raw(url), filename)

    def head(self, url: str, allow_redirects: bool = False) -> requests.Response:
        """HEAD a URL anonymously.

        :raises QueryReturnedNotFoundException: When the server responds with a 404.
        :raises QueryReturnedForbiddenException: When the server responds with a 403.
        :raises ConnectionException: When request failed.

        .. versionadded:: 4.7.6
        """
        with self.get_anonymous_session() as anonymous_session:
            resp = anonymous_session.head(url, allow_redirects=allow_redirects)
        if resp.status_code == 200:
            return resp
        else:
            if resp.status_code == 403:
                # suspected invalid URL signature
                raise QueryReturnedForbiddenException(self._response_error(resp))
            if resp.status_code == 404:
                # 404 not worth retrying.
                raise QueryReturnedNotFoundException(self._response_error(resp))
            raise ConnectionException(self._response_error(resp))

    @property
    def root_rhx_gis(self) -> Optional[str]:
        """rhx_gis string returned in the / query."""
        if self.is_logged_in:
            # At the moment, rhx_gis seems to be required for anonymous requests only. By returning None when logged
            # in, we can save the root_rhx_gis lookup query.
            return None
        if self._root_rhx_gis is None:
            self._root_rhx_gis = self.get_json('', {}).get('rhx_gis', '')
        return self._root_rhx_gis or None


class RateController:
    """
    Class providing request tracking and rate controlling to stay within rate limits.

    It can be overridden to change Instaloader's behavior regarding rate limits, for example to raise a custom
    exception when the rate limit is hit::

       import instaloader

       class MyRateController(instaloader.RateController):
           def sleep(self, secs):
               raise MyCustomException()

       L = instaloader.Instaloader(rate_controller=lambda ctx: MyRateController(ctx))
    """

    def __init__(self, context: InstaloaderContext):
        self._context = context
        self._query_timestamps: Dict[str, List[float]] = dict()
        self._earliest_next_request_time = 0.0
        self._iphone_earliest_next_request_time = 0.0

    def sleep(self, secs: float):
        """Wait given number of seconds."""
        # Not static, to allow for the behavior of this method to depend on context-inherent properties, such as
        # whether we are logged in.
        time.sleep(secs)

    def _dump_query_timestamps(self, current_time: float, failed_query_type: str):
        windows = [10, 11, 20, 22, 30, 60]
        self._context.error("Number of requests within last {} minutes grouped by type:"
                            .format('/'.join(str(w) for w in windows)),
                            repeat_at_end=False)
        for query_type, times in self._query_timestamps.items():
            reqs_in_sliding_window = [sum(t > current_time - w * 60 for t in times) for w in windows]
            self._context.error(" {} {:>32}: {}".format(
                "*" if query_type == failed_query_type else " ",
                query_type,
                " ".join("{:4}".format(reqs) for reqs in reqs_in_sliding_window)
            ), repeat_at_end=False)

    def count_per_sliding_window(self, query_type: str) -> int:
        """Return how many requests of the given type can be done within a sliding window of 11 minutes.

        This is called by :meth:`RateController.query_waittime` and allows to simply customize wait times before queries
        at query_type granularity. Consider overriding :meth:`RateController.query_waittime` directly if you need more
        control."""
        # Not static, to allow for the count_per_sliding_window to depend on context-inherent properties, such as
        # whether we are logged in.
        return 75 if query_type == 'other' else 200

    def _reqs_in_sliding_window(self, query_type: Optional[str], current_time: float, window: float) -> List[float]:
        if query_type is not None:
            # timestamps of type query_type
            relevant_timestamps = self._query_timestamps[query_type]
        else:
            # all GraphQL queries, i.e. not 'iphone' or 'other'
            graphql_query_timestamps = filter(lambda tp: tp[0] not in ['iphone', 'other'],
                                              self._query_timestamps.items())
            relevant_timestamps = [t for times in (tp[1] for tp in graphql_query_timestamps) for t in times]
        return list(filter(lambda t: t > current_time - window, relevant_timestamps))

    def query_waittime(self, query_type: str, current_time: float, untracked_queries: bool = False) -> float:
        """Calculate time needed to wait before query can be executed."""
        per_type_sliding_window = 660
        iphone_sliding_window = 1800
        if query_type not in self._query_timestamps:
            self._query_timestamps[query_type] = []
        self._query_timestamps[query_type] = list(filter(lambda t: t > current_time - 60 * 60,
                                                         self._query_timestamps[query_type]))

        def per_type_next_request_time():
            reqs_in_sliding_window = self._reqs_in_sliding_window(query_type, current_time, per_type_sliding_window)
            if len(reqs_in_sliding_window) < self.count_per_sliding_window(query_type):
                return 0.0
            else:
                return min(reqs_in_sliding_window) + per_type_sliding_window + 6

        def gql_accumulated_next_request_time():
            if query_type in ['iphone', 'other']:
                return 0.0
            gql_accumulated_sliding_window = 600
            gql_accumulated_max_count = 275
            reqs_in_sliding_window = self._reqs_in_sliding_window(None, current_time, gql_accumulated_sliding_window)
            if len(reqs_in_sliding_window) < gql_accumulated_max_count:
                return 0.0
            else:
                return min(reqs_in_sliding_window) + gql_accumulated_sliding_window

        def untracked_next_request_time():
            if untracked_queries:
                if query_type == "iphone":
                    reqs_in_sliding_window = self._reqs_in_sliding_window(query_type, current_time,
                                                                          iphone_sliding_window)
                    self._iphone_earliest_next_request_time = min(reqs_in_sliding_window) + iphone_sliding_window + 18
                else:
                    reqs_in_sliding_window = self._reqs_in_sliding_window(query_type, current_time,
                                                                          per_type_sliding_window)
                    self._earliest_next_request_time = min(reqs_in_sliding_window) + per_type_sliding_window + 6
            return max(self._iphone_earliest_next_request_time, self._earliest_next_request_time)

        def iphone_next_request():
            if query_type == "iphone":
                reqs_in_sliding_window = self._reqs_in_sliding_window(query_type, current_time, iphone_sliding_window)
                if len(reqs_in_sliding_window) >= 199:
                    return min(reqs_in_sliding_window) + iphone_sliding_window + 18
            return 0.0

        return max(0.0,
                   max(
                       per_type_next_request_time(),
                       gql_accumulated_next_request_time(),
                       untracked_next_request_time(),
                       iphone_next_request(),
                   ) - current_time)

    def wait_before_query(self, query_type: str) -> None:
        """This method is called before a query to Instagram.

        It calls :meth:`RateController.query_waittime` to determine the time needed to wait and then calls
        :meth:`RateController.sleep` to wait until the request can be made."""
        waittime = self.query_waittime(query_type, time.monotonic(), False)
        assert waittime >= 0
        if waittime > 15:
            formatted_waittime = ("{} seconds".format(round(waittime)) if waittime <= 666 else
                                  "{} minutes".format(round(waittime / 60)))
            self._context.log("\nToo many queries in the last time. Need to wait {}, until {:%H:%M}."
                              .format(formatted_waittime, datetime.now() + timedelta(seconds=waittime)))
        if waittime > 0:
            self.sleep(waittime)
        if query_type not in self._query_timestamps:
            self._query_timestamps[query_type] = [time.monotonic()]
        else:
            self._query_timestamps[query_type].append(time.monotonic())

    def handle_429(self, query_type: str) -> None:
        """This method is called to handle a 429 Too Many Requests response.

        It calls :meth:`RateController.query_waittime` to determine the time needed to wait and then calls
        :meth:`RateController.sleep` to wait until we can repeat the same request."""
        current_time = time.monotonic()
        waittime = self.query_waittime(query_type, current_time, True)
        assert waittime >= 0
        self._dump_query_timestamps(current_time, query_type)
        text_for_429 = ("Instagram responded with HTTP error \"429 - Too Many Requests\". Please do not run multiple "
                        "instances of Instaloader in parallel or within short sequence. Also, do not use any Instagram "
                        "App while Instaloader is running.")
        self._context.error(textwrap.fill(text_for_429), repeat_at_end=False)
        if waittime > 1.5:
            formatted_waittime = ("{} seconds".format(round(waittime)) if waittime <= 666 else
                                  "{} minutes".format(round(waittime / 60)))
            self._context.error("The request will be retried in {}, at {:%H:%M}."
                                .format(formatted_waittime, datetime.now() + timedelta(seconds=waittime)),
                                repeat_at_end=False)
        if waittime > 0:
            self.sleep(waittime)
