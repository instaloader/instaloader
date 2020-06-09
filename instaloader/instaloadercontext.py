import base64
import hashlib
import json
import os
import pickle
import random
import re
import shutil
import sys
import textwrap
import time
import urllib.parse
from contextlib import contextmanager
from datetime import datetime, timedelta
from functools import partial
from typing import Any, Callable, Dict, Iterator, List, Optional, Union, Tuple

import requests
import requests.utils
from Crypto import Random
from Crypto.Cipher import AES
from nacl.public import PublicKey, SealedBox  # type:ignore

from .exceptions import *


def copy_session(session: requests.Session, request_timeout: Optional[float] = None) -> requests.Session:
    """Duplicates a requests.Session."""
    new = requests.Session()
    new.cookies = requests.utils.cookiejar_from_dict(requests.utils.dict_from_cookiejar(session.cookies))
    new.headers = session.headers.copy()
    if request_timeout is not None:
        # Override default timeout behavior.
        # Need to silence mypy bug for this. See: https://github.com/python/mypy/issues/2427
        new.request = partial(new.request, timeout=request_timeout) # type: ignore
    return new


def default_user_agent() -> str:
    return 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 ' \
           '(KHTML, like Gecko) Chrome/51.0.2704.79 Safari/537.36'


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
                 max_connection_attempts: int = 3, request_timeout: Optional[float] = None,
                 rate_controller: Optional[Callable[["InstaloaderContext"], "RateController"]] = None):

        self.user_agent = user_agent if user_agent is not None else default_user_agent()
        self.request_timeout = request_timeout
        self._session = self.get_anonymous_session()
        self.username = None
        self.sleep = sleep
        self.quiet = quiet
        self.max_connection_attempts = max_connection_attempts
        self._graphql_page_length = 50
        self._root_rhx_gis = None
        self.two_factor_auth_pending = None

        # error log, filled with error() and printed at the end of Instaloader.main()
        self.error_log = []                      # type: List[str]

        self._rate_controller = rate_controller(self) if rate_controller is not None else RateController(self)

        # Can be set to True for testing, disables supression of InstaloaderContext._error_catcher
        self.raise_all_errors = False

        # Cache profile from id (mapping from id to Profile)
        self.profile_id_cache = dict()           # type: Dict[int, Any]

    @contextmanager
    def anonymous_copy(self):
        session = self._session
        username = self.username
        self._session = self.get_anonymous_session()
        self.username = None
        try:
            yield self
        finally:
            self._session.close()
            self.username = username
            self._session = session

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
            del header['Referer']
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
        if self.request_timeout is not None:
            # Override default timeout behavior.
            # Need to silence mypy bug for this. See: https://github.com/python/mypy/issues/2427
            session.request = partial(session.request, timeout=self.request_timeout) # type: ignore
        return session

    def save_session_to_file(self, sessionfile):
        """Not meant to be used directly, use :meth:`Instaloader.save_session_to_file`."""
        pickle.dump(requests.utils.dict_from_cookiejar(self._session.cookies), sessionfile)

    def load_session_from_file(self, username, sessionfile):
        """Not meant to be used directly, use :meth:`Instaloader.load_session_from_file`."""
        session = requests.Session()
        session.cookies = requests.utils.cookiejar_from_dict(pickle.load(sessionfile))
        session.headers.update(self._default_http_header())
        session.headers.update({'X-CSRFToken': session.cookies.get_dict()['csrftoken']})
        if self.request_timeout is not None:
            # Override default timeout behavior.
            # Need to silence mypy bug for this. See: https://github.com/python/mypy/issues/2427
            session.request = partial(session.request, timeout=self.request_timeout) # type: ignore
        self._session = session
        self.username = username

    def test_login(self) -> Optional[str]:
        """Not meant to be used directly, use :meth:`Instaloader.test_login`."""
        data = self.graphql_query("d6f4427fbe92d846298cf93df0b937d3", {})
        return data["data"]["user"]["username"] if data["data"]["user"] is not None else None

    def login(self, user, passwd):
        """Not meant to be used directly, use :meth:`Instaloader.login`.

        :raises InvalidArgumentException: If the provided username does not exist.
        :raises BadCredentialsException: If the provided password is wrong.
        :raises ConnectionException: If connection to Instagram failed.
        :raises TwoFactorAuthRequiredException: First step of 2FA login done, now call
           :meth:`Instaloader.two_factor_login`."""
        # pylint:disable=import-outside-toplevel
        import http.client
        # pylint:disable=protected-access
        http.client._MAXHEADERS = 200
        session = requests.Session()
        session.cookies.update({'sessionid': '', 'mid': '', 'ig_pr': '1',
                                'ig_vw': '1920', 'ig_cb': '1', 'csrftoken': '',
                                's_network': '', 'ds_user_id': ''})
        session.headers.update(self._default_http_header())
        if self.request_timeout is not None:
            # Override default timeout behavior.
            # Need to silence mypy bug for this. See: https://github.com/python/mypy/issues/2427
            session.request = partial(session.request, timeout=self.request_timeout) # type: ignore
        session.get('https://www.instagram.com/web/__mid/')
        csrf_token = session.cookies.get_dict()['csrftoken']
        session.headers.update({'X-CSRFToken': csrf_token})
        # Not using self.get_json() here, because we need to access csrftoken cookie
        self.do_sleep()
        enc_password = self._get_encrypted_password(passwd)
        login = session.post('https://www.instagram.com/accounts/login/ajax/',
                             data={'enc_password': enc_password, 'username': user}, allow_redirects=True)
        try:
            resp_json = login.json()
        except json.decoder.JSONDecodeError:
            raise ConnectionException("Login error: JSON decode fail, {} - {}.".format(login.status_code, login.reason))
        if resp_json.get('two_factor_required'):
            two_factor_session = copy_session(session, self.request_timeout)
            two_factor_session.headers.update({'X-CSRFToken': csrf_token})
            two_factor_session.cookies.update({'csrftoken': csrf_token})
            self.two_factor_auth_pending = (two_factor_session,
                                            user,
                                            resp_json['two_factor_info']['two_factor_identifier'])
            raise TwoFactorAuthRequiredException("Login error: two-factor authentication required.")
        if resp_json.get('checkpoint_url'):
            raise ConnectionException("Login: Checkpoint required. Point your browser to "
                                      "https://www.instagram.com{} - "
                                      "follow the instructions, then retry.".format(resp_json.get('checkpoint_url')))
        if resp_json['status'] != 'ok':
            if 'message' in resp_json:
                raise ConnectionException("Login error: \"{}\" status, message \"{}\".".format(resp_json['status'],
                                                                                               resp_json['message']))
            else:
                raise ConnectionException("Login error: \"{}\" status.".format(resp_json['status']))
        if 'authenticated' not in resp_json:
            # Issue #472
            if 'message' in resp_json:
                raise ConnectionException("Login error: Unexpected response, \"{}\".".format(resp_json['message']))
            else:
                raise ConnectionException("Login error: Unexpected response, this might indicate a blocked IP.")
        if not resp_json['authenticated']:
            if resp_json['user']:
                # '{"authenticated": false, "user": true, "status": "ok"}'
                raise BadCredentialsException('Login error: Wrong password.')
            else:
                # '{"authenticated": false, "user": false, "status": "ok"}'
                # Raise InvalidArgumentException rather than BadCredentialException, because BadCredentialException
                # triggers re-asking of password in Instaloader.interactive_login(), which makes no sense if the
                # username is invalid.
                raise InvalidArgumentException('Login error: User {} does not exist.'.format(user))
        # '{"authenticated": true, "user": true, "userId": ..., "oneTapPrompt": false, "status": "ok"}'
        session.headers.update({'X-CSRFToken': login.cookies['csrftoken']})
        self._session = session
        self.username = user

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
                raise BadCredentialsException("Login error: {}".format(resp_json['message']))
            else:
                raise BadCredentialsException("Login error: \"{}\" status.".format(resp_json['status']))
        session.headers.update({'X-CSRFToken': login.cookies['csrftoken']})
        self._session = session
        self.username = user
        self.two_factor_auth_pending = None

    def do_sleep(self):
        """Sleep a short time if self.sleep is set. Called before each request to instagram.com."""
        if self.sleep:
            time.sleep(min(random.expovariate(0.7), 5.0))

    def get_json(self, path: str, params: Dict[str, Any], host: str = 'www.instagram.com',
                 session: Optional[requests.Session] = None, _attempt=1) -> Dict[str, Any]:
        """JSON request to Instagram.

        :param path: URL, relative to the given domain which defaults to www.instagram.com/
        :param params: GET parameters
        :param host: Domain part of the URL from where to download the requested JSON; defaults to www.instagram.com
        :param session: Session to use, or None to use self.session
        :return: Decoded response dictionary
        :raises QueryReturnedBadRequestException: When the server responds with a 400.
        :raises QueryReturnedNotFoundException: When the server responds with a 404.
        :raises ConnectionException: When query repeatedly failed.
        """
        is_graphql_query = 'query_hash' in params and 'graphql/query' in path
        is_iphone_query = host == 'i.instagram.com'
        is_other_query = not is_graphql_query and host == "www.instagram.com"
        sess = session if session else self._session
        try:
            self.do_sleep()
            if is_graphql_query:
                self._rate_controller.wait_before_query(params['query_hash'])
            if is_iphone_query:
                self._rate_controller.wait_before_query('iphone')
            if is_other_query:
                self._rate_controller.wait_before_query('other')
            resp = sess.get('https://{0}/{1}'.format(host, path), params=params, allow_redirects=False)
            while resp.is_redirect:
                redirect_url = resp.headers['location']
                self.log('\nHTTP redirect from https://{0}/{1} to {2}'.format(host, path, redirect_url))
                if redirect_url.startswith('https://www.instagram.com/accounts/login'):
                    # alternate rate limit exceeded behavior
                    raise TooManyRequestsException("429 Too Many Requests: redirected to login")
                if redirect_url.startswith('https://{}/'.format(host)):
                    resp = sess.get(redirect_url if redirect_url.endswith('/') else redirect_url + '/',
                                    params=params, allow_redirects=False)
                else:
                    break
            if resp.status_code == 400:
                raise QueryReturnedBadRequestException("400 Bad Request")
            if resp.status_code == 404:
                raise QueryReturnedNotFoundException("404 Not Found")
            if resp.status_code == 429:
                raise TooManyRequestsException("429 Too Many Requests")
            if resp.status_code != 200:
                raise ConnectionException("HTTP error code {}.".format(resp.status_code))
            is_html_query = not is_graphql_query and not "__a" in params and host == "www.instagram.com"
            if is_html_query:
                match = re.search(r'window\._sharedData = (.*);</script>', resp.text)
                if match is None:
                    raise QueryReturnedNotFoundException("Could not find \"window._sharedData\" in html response.")
                resp_json = json.loads(match.group(1))
                entry_data = resp_json.get('entry_data')
                post_or_profile_page = list(entry_data.values())[0] if entry_data is not None else None
                if post_or_profile_page is None:
                    raise ConnectionException("\"window._sharedData\" does not contain required keys.")
                # If GraphQL data is missing in `window._sharedData`, search for it in `__additionalDataLoaded`.
                if 'graphql' not in post_or_profile_page[0]:
                    match = re.search(r'window\.__additionalDataLoaded\([^{]+{"graphql":({.*})}\);</script>',
                                      resp.text)
                    if match is not None:
                        post_or_profile_page[0]['graphql'] = json.loads(match.group(1))
                return resp_json
            else:
                resp_json = resp.json()
            if 'status' in resp_json and resp_json['status'] != "ok":
                if 'message' in resp_json:
                    raise ConnectionException("Returned \"{}\" status, message \"{}\".".format(resp_json['status'],
                                                                                               resp_json['message']))
                else:
                    raise ConnectionException("Returned \"{}\" status.".format(resp_json['status']))
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
                    if is_iphone_query:
                        self._rate_controller.handle_429('iphone')
                    if is_other_query:
                        self._rate_controller.handle_429('other')
                return self.get_json(path=path, params=params, host=host, session=sess, _attempt=_attempt + 1)
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
            tempsession.headers['User-Agent'] = 'Instagram 123.1.0.26.115 (iPhone12,1; iOS 13_3; en_US; en-US; ' \
                                                'scale=2.00; 1656x3584; 190542906)'
            for header in ['Host', 'Origin', 'X-Instagram-AJAX', 'X-Requested-With']:
                tempsession.headers.pop(header, None)
            return self.get_json(path, params, 'i.instagram.com', tempsession)

    def write_raw(self, resp: Union[bytes, requests.Response], filename: str) -> None:
        """Write raw response data into a file.

        .. versionadded:: 4.2.1"""
        self.log(filename, end=' ', flush=True)
        with open(filename + '.temp', 'wb') as file:
            if isinstance(resp, requests.Response):
                shutil.copyfileobj(resp.raw, file)
            else:
                file.write(resp)
        os.rename(filename + '.temp', filename)

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
                raise QueryReturnedForbiddenException("403 when accessing {}.".format(url))
            if resp.status_code == 404:
                # 404 not worth retrying.
                raise QueryReturnedNotFoundException("404 when accessing {}.".format(url))
            raise ConnectionException("HTTP error code {}.".format(resp.status_code))

    def get_and_write_raw(self, url: str, filename: str) -> None:
        """Downloads and writes anonymously-requested raw data into a file.

        :raises QueryReturnedNotFoundException: When the server responds with a 404.
        :raises QueryReturnedForbiddenException: When the server responds with a 403.
        :raises ConnectionException: When download repeatedly failed."""
        self.write_raw(self.get_raw(url), filename)

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

    def _get_encryption_data(self) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        resp = self._session.get("https://www.instagram.com/accounts/login/")
        return (resp.headers.get("ig-set-password-encryption-web-key-id"),
                resp.headers.get("ig-set-password-encryption-web-key-version"),
                resp.headers.get("ig-set-password-encryption-web-pub-key"))

    def _get_encrypted_password(self, password):
        # contributed by @twitter-79 in
        # https://github.com/instaloader/instaloader/issues/615#issuecomment-630631930
        key_id, app_id, public_key = self._get_encryption_data()
        timestamp = str(int(datetime.now().timestamp()))

        # create a random key of length 32 bytes (for AES 256)
        key = Random.get_random_bytes(32)
        # create a buffer of length 12 bytes filled with 0
        iv = bytearray(12)

        aes = AES.new(key, AES.MODE_GCM, nonce=iv)
        aes.update(bytearray(timestamp, 'utf-8'))
        ciphertext, tag = aes.encrypt_and_digest(bytearray(password, 'utf-8'))

        # get a byte array of the given public key
        public_key_seal = PublicKey(bytes.fromhex(public_key))
        sealed_box = SealedBox(public_key_seal)
        sealed = sealed_box.encrypt(key)

        enc_password = bytearray()
        enc_password += bytearray(
            [1, int(key_id), len(sealed) & 255, (len(sealed) >> 8) & 255]) + sealed + tag + ciphertext

        return ('#PWD_INSTAGRAM_BROWSER' + ':' + app_id + ':' + timestamp + ':' +
                str(base64.b64encode(enc_password), 'utf-8'))


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
        self._graphql_query_timestamps = dict()  # type: Dict[str, List[float]]
        self._graphql_earliest_next_request_time = 0.0

    def sleep(self, secs: float):
        """Wait given number of seconds."""
        # Not static, to allow for the behavior of this method to depend on context-inherent properties, such as
        # whether we are logged in.
        # pylint:disable=no-self-use
        time.sleep(secs)

    def _dump_query_timestamps(self, current_time: float):
        windows = [10, 11, 15, 20, 30, 60]
        print("GraphQL requests:", file=sys.stderr)
        for query_hash, times in self._graphql_query_timestamps.items():
            print("  {}".format(query_hash), file=sys.stderr)
            for window in windows:
                reqs_in_sliding_window = sum(t > current_time - window * 60 for t in times)
                print("    last {} minutes: {} requests".format(window, reqs_in_sliding_window), file=sys.stderr)

    def count_per_sliding_window(self, query_type: str) -> int:
        """Return how many GraphQL requests can be done within the sliding window."""
        # Not static, to allow for the count_per_sliding_window to depend on context-inherent properties, such as
        # whether we are logged in.
        # pylint:disable=no-self-use,unused-argument
        return 200

    def query_waittime(self, query_type: str, current_time: float, untracked_queries: bool = False) -> float:
        """Calculate time needed to wait before GraphQL query can be executed."""
        sliding_window = 660
        if query_type not in self._graphql_query_timestamps:
            self._graphql_query_timestamps[query_type] = []
        self._graphql_query_timestamps[query_type] = list(filter(lambda t: t > current_time - 60 * 60,
                                                                 self._graphql_query_timestamps[query_type]))
        reqs_in_sliding_window = list(filter(lambda t: t > current_time - sliding_window,
                                             self._graphql_query_timestamps[query_type]))
        count_per_sliding_window = self.count_per_sliding_window(query_type)
        if len(reqs_in_sliding_window) < count_per_sliding_window and not untracked_queries:
            return max(0.0, self._graphql_earliest_next_request_time - current_time)
        next_request_time = min(reqs_in_sliding_window) + sliding_window + 6
        if untracked_queries:
            self._graphql_earliest_next_request_time = next_request_time
        return max(next_request_time, self._graphql_earliest_next_request_time) - current_time

    def wait_before_query(self, query_type: str) -> None:
        """This method is called before a query to Instagram. It calls :meth:`RateController.sleep` to wait
        until the request can be made."""
        waittime = self.query_waittime(query_type, time.monotonic(), False)
        assert waittime >= 0
        if waittime > 15:
            self._context.log("\nToo many queries in the last time. Need to wait {} seconds, until {:%H:%M}."
                              .format(round(waittime), datetime.now() + timedelta(seconds=waittime)))
        if waittime > 0:
            self.sleep(waittime)
        if query_type not in self._graphql_query_timestamps:
            self._graphql_query_timestamps[query_type] = [time.monotonic()]
        else:
            self._graphql_query_timestamps[query_type].append(time.monotonic())

    def handle_429(self, query_type: str) -> None:
        """This method is called to handle a 429 Too Many Requests response. It calls :meth:`RateController.sleep` to
         wait until we can repeat the same request."""
        text_for_429 = ("HTTP error code 429 was returned because too many queries occurred in the last time. "
                        "Please do not use Instagram in your browser or run multiple instances of Instaloader "
                        "in parallel.")
        print(textwrap.fill(text_for_429), file=sys.stderr)
        current_time = time.monotonic()
        waittime = self.query_waittime(query_type, current_time, True)
        assert waittime >= 0
        if waittime > 15:
            self._context.log("The request will be retried in {} seconds, at {:%H:%M}."
                              .format(round(waittime), datetime.now() + timedelta(seconds=waittime)))
        self._dump_query_timestamps(current_time)
        if waittime > 0:
            self.sleep(waittime)
