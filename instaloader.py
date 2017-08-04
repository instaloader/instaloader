#!/usr/bin/env python3

"""Download pictures (or videos) along with their captions and other metadata from Instagram."""

import getpass
import json
import os
import pickle
import random
import re
import shutil
import string
import sys
import tempfile
import time
from argparse import ArgumentParser
from base64 import b64decode, b64encode
from datetime import datetime
from io import BytesIO
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests
import requests.utils
import urllib3


# To get version from setup.py for instaloader --version
import pkg_resources
try:
    # pylint:disable=no-member
    __version__ = pkg_resources.get_distribution('instaloader').version
except pkg_resources.DistributionNotFound:
    __version__ = 'Run ./setup.py --version'

try:
    # pylint:disable=wrong-import-position
    import win_unicode_console
except ImportError:
    WINUNICODE = False
else:
    win_unicode_console.enable()
    WINUNICODE = True


class InstaloaderException(Exception):
    """Base exception for this script"""
    pass


class NonfatalException(InstaloaderException):
    """Base exception for errors which should not cause instaloader to stop"""
    pass


class ProfileNotExistsException(NonfatalException):
    pass


class ProfileAccessDeniedException(NonfatalException):
    pass


class ProfileHasNoPicsException(NonfatalException):
    pass


class PrivateProfileNotFollowedException(NonfatalException):
    pass


class LoginRequiredException(NonfatalException):
    pass


class InvalidArgumentException(NonfatalException):
    pass


class BadResponseException(NonfatalException):
    pass


class NodeUnavailableException(NonfatalException):
    pass


class BadCredentialsException(InstaloaderException):
    pass


class ConnectionException(InstaloaderException):
    pass


def get_default_session_filename(username: str) -> str:
    """Returns default session filename for given username."""
    dirname = tempfile.gettempdir() + "/" + ".instaloader-" + getpass.getuser()
    filename = dirname + "/" + "session-" + username
    return filename.lower()


def copy_session(session: requests.Session) -> requests.Session:
    """Duplicates a requests.Session."""
    new = requests.Session()
    new.cookies = \
        requests.utils.cookiejar_from_dict(requests.utils.dict_from_cookiejar(session.cookies))
    new.headers = session.headers.copy()
    return new


def default_user_agent() -> str:
    return 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 ' \
           '(KHTML, like Gecko) Chrome/51.0.2704.79 Safari/537.36'


def shortcode_to_mediaid(code: str) -> int:
    if len(code) > 11:
        raise InvalidArgumentException("Wrong shortcode \"{0}\", unable to convert to mediaid.".format(code))
    code = 'A' * (12 - len(code)) + code
    return int.from_bytes(b64decode(code.encode(), b'-_'), 'big')


def mediaid_to_shortcode(mediaid: int) -> str:
    if mediaid.bit_length() > 64:
        raise InvalidArgumentException("Wrong mediaid {0}, unable to convert to shortcode".format(str(mediaid)))
    return b64encode(mediaid.to_bytes(9, 'big'), b'-_').decode().replace('A', ' ').lstrip().replace(' ','A')


def format_string_contains_key(format_string: str, key: str) -> bool:
    # pylint:disable=unused-variable
    for literal_text, field_name, format_spec, conversion in string.Formatter().parse(format_string):
        if field_name == key:
            return True
    return False


class Instaloader:
    def __init__(self,
                 sleep: bool = True, quiet: bool = False, shorter_output: bool = False,
                 user_agent: Optional[str] = None,
                 dirname_pattern: Optional[str] = None,
                 filename_pattern: Optional[str] = None):
        self.user_agent = user_agent if user_agent is not None else default_user_agent()
        self.session = self.get_anonymous_session()
        self.username = None
        self.sleep = sleep
        self.quiet = quiet
        self.shorter_output = shorter_output
        self.dirname_pattern = dirname_pattern if dirname_pattern is not None else '{target}'
        self.filename_pattern = filename_pattern.replace('{date}', '{date:%Y-%m-%d_%H-%M-%S}') \
            if filename_pattern is not None else '{date:%Y-%m-%d_%H-%M-%S}'

    def _log(self, *msg, sep='', end='\n', flush=False):
        if not self.quiet:
            print(*msg, sep=sep, end=end, flush=flush)

    def _sleep(self):
        """Sleep a short, random time if self.sleep is set. Called before each request to the instagram.com."""
        if self.sleep:
            time.sleep(random.uniform(0.25, 2.0))

    def _get_and_write_raw(self, url: str, filename: str, tries: int = 3) -> None:
        try:
            resp = self.get_anonymous_session().get(url, stream=True)
            if resp.status_code == 200:
                self._log(filename, end=' ', flush=True)
                with open(filename, 'wb') as file:
                    resp.raw.decode_content = True
                    shutil.copyfileobj(resp.raw, file)
            else:
                raise ConnectionException("Request returned HTTP error code {}.".format(resp.status_code))
        except (urllib3.exceptions.HTTPError, requests.exceptions.RequestException, ConnectionException) as err:
            print("URL: {}\n{}".format(url, err), file=sys.stderr)
            if tries <= 1:
                raise NodeUnavailableException
            self._sleep()
            self._get_and_write_raw(url, filename, tries - 1)

    def get_json(self, name: str, session: requests.Session = None,
                 max_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Return JSON of a profile"""
        if session is None:
            session = self.session
        self._sleep()
        if not max_id:
            resp = session.get('https://www.instagram.com/' + name)
        else:
            resp = session.get('https://www.instagram.com/' + name, params={'max_id': max_id})
        match = re.search('window\\._sharedData = .*<', resp.text)
        if match is not None:
            return json.loads(match.group(0)[21:-2])

    def default_http_header(self, empty_session_only: bool = False) -> Dict[str, str]:
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
        session.headers.update(self.default_http_header(empty_session_only=True))
        return session

    def graphql_query(self, query_id: int, variables: Dict[str, Any],
                      referer: Optional[str] = None) -> Dict[str, Any]:
        """
        Do a GraphQL Query.

        :param query_id: Query ID.
        :param variables: Variables for the Query.
        :param referer: HTTP Referer, or None.
        :return: The server's response dictionary.
        """
        tmpsession = copy_session(self.session)
        tmpsession.headers.update(self.default_http_header(empty_session_only=True))
        del tmpsession.headers['Connection']
        del tmpsession.headers['Content-Length']
        tmpsession.headers['authority'] = 'www.instagram.com'
        tmpsession.headers['scheme'] = 'https'
        tmpsession.headers['accept'] = '*/*'
        if referer is not None:
            tmpsession.headers['referer'] = referer
        self._sleep()
        response = tmpsession.get('https://www.instagram.com/graphql/query',
                                  params={'query_id': query_id,
                                          'variables': json.dumps(variables, separators=(',', ':'))})
        if response.status_code != 200:
            raise ConnectionException("GraphQL query returned HTTP error code {}.".format(response.status_code))
        return response.json()

    def get_username_by_id(self, profile_id: int) -> str:
        """To get the current username of a profile, given its unique ID, this function can be used."""
        data = self.graphql_query(17862015703145017, {'id': str(profile_id), 'first': 1})['data']['user']
        if data:
            data = data["edge_owner_to_timeline_media"]
        else:
            raise ProfileNotExistsException("No profile found, the user may have blocked you (ID: " +
                                            str(profile_id) + ").")
        if not data['edges']:
            if data['count'] == 0:
                raise ProfileHasNoPicsException("Profile with ID {0}: no pics found.".format(str(profile_id)))
            else:
                raise LoginRequiredException("Login required to determine username (ID: " + str(profile_id) + ").")
        else:
            shortcode = mediaid_to_shortcode(int(data['edges'][0]["node"]["id"]))
            data = self.get_json("p/" + shortcode)
            return data['entry_data']['PostPage'][0]['graphql']['shortcode_media']['owner']['username']

    def get_id_by_username(self, profile: str) -> int:
        """Each Instagram profile has its own unique ID which stays unmodified even if a user changes
        his/her username. To get said ID, given the profile's name, you may call this function."""
        data = self.get_json(profile, session=self.get_anonymous_session())
        if "ProfilePage" not in data["entry_data"]:
            raise ProfileNotExistsException("Profile {0} does not exist.".format(profile))
        return int(data['entry_data']['ProfilePage'][0]['user']['id'])

    def get_followers(self, profile: str) -> List[Dict[str, Any]]:
        """
        Retrieve list of followers of given profile.
        To use this, one needs to be logged in and private profiles has to be followed,
        otherwise this returns an empty list.

        :param profile: Name of profile to lookup followers.
        :return: List of followers (list of dictionaries).
        """
        profile_id = self.get_id_by_username(profile)
        data = self.graphql_query(17851374694183129, {'id': str(profile_id),
                                                      'first': 500},
                                  referer='https://www.instagram.com/' + profile + '/')
        followers = []
        while True:
            edge_followed_by = data['data']['user']['edge_followed_by']
            followers.extend([follower['node'] for follower in edge_followed_by['edges']])
            page_info = edge_followed_by['page_info']
            if page_info['has_next_page']:
                data = self.graphql_query(17851374694183129, {'id': str(profile_id),
                                                              'first': 500,
                                                              'after': page_info['end_cursor']},
                                          referer='https://www.instagram.com/' + profile + '/')
            else:
                break
        return followers

    def get_followees(self, profile: str) -> List[Dict[str, Any]]:
        """
        Retrieve list of followees (followings) of given profile.
        To use this, one needs to be logged in and private profiles has to be followed,
        otherwise this returns an empty list.

        :param profile: Name of profile to lookup followers.
        :return: List of followees (list of dictionaries).
        """
        profile_id = self.get_id_by_username(profile)
        data = self.graphql_query(17874545323001329, {'id': profile_id,
                                                      'first': 500},
                                  referer='https://www.instagram.com/' + profile + '/')
        followees = []
        while True:
            edge_follow = data['data']['user']['edge_follow']
            followees.extend([followee['node'] for followee in edge_follow['edges']])
            page_info = edge_follow['page_info']
            if page_info['has_next_page']:
                data = self.graphql_query(17874545323001329, {'id': profile_id,
                                                              'first': 500,
                                                              'after': page_info['end_cursor']},
                                          referer='https://www.instagram.com/' + profile + '/')
            else:
                break
        return followees

    def get_comments(self, shortcode: str) -> List[Dict[str, Any]]:
        """Retrieve comments of node with given shortcode."""
        data = self.graphql_query(17852405266163336, {'shortcode': shortcode,
                                                      'first': 500},
                                  referer='https://www.instagram.com/p/' + shortcode + '/')
        comments = []
        while True:
            edge_media_to_comment = data['data']['shortcode_media']['edge_media_to_comment']
            comments.extend([comment['node'] for comment in edge_media_to_comment['edges']])
            page_info = edge_media_to_comment['page_info']
            if page_info['has_next_page']:
                data = self.graphql_query(17852405266163336, {'shortcode': shortcode,
                                                              'first': 500,
                                                              'after': page_info['end_cursor']},
                                          referer='https://www.instagram.com/p/' + shortcode + '/')
            else:
                break
        return comments

    def download_pic(self, filename: str, url: str, mtime: datetime,
                     filename_suffix: Optional[str] = None) -> bool:
        """Downloads and saves picture with given url under given directory with given timestamp.
        Returns true, if file was actually downloaded, i.e. updated."""
        urlmatch = re.search('\\.[a-z]*\\?', url)
        file_extension = url[-3:] if urlmatch is None else urlmatch.group(0)[1:-1]
        if filename_suffix is not None:
            filename += '_' + filename_suffix
        filename += '.' + file_extension
        if os.path.isfile(filename):
            self._log(filename + ' exists', end=' ', flush=True)
            return False
        self._get_and_write_raw(url, filename)
        os.utime(filename, (datetime.now().timestamp(), mtime.timestamp()))
        return True

    def update_comments(self, filename: str, shortcode: str) -> None:
        filename += '_comments.json'
        try:
            comments = json.load(open(filename))
        except FileNotFoundError:
            comments = list()
        comments.extend(self.get_comments(shortcode))
        if comments:
            with open(filename, 'w') as file:
                comments_list = sorted(sorted(list(comments), key=lambda t: t['id']),
                                       key=lambda t: t['created_at'], reverse=True)
                unique_comments_list = [comments_list[0]]
                #for comment in comments_list:
                #    if unique_comments_list[-1]['id'] != comment['id']:
                #        unique_comments_list.append(comment)
                #file.write(json.dumps(unique_comments_list, indent=4))
                #pylint:disable=invalid-name
                for x, y in zip(comments_list[:-1], comments_list[1:]):
                    if x['id'] != y['id']:
                        unique_comments_list.append(y)
                file.write(json.dumps(unique_comments_list, indent=4))
            self._log('comments', end=' ', flush=True)

    def save_caption(self, filename: str, mtime: datetime, caption: str) -> None:
        """Updates picture caption"""
        filename += '.txt'
        pcaption = caption.replace('\n', ' ').strip()
        caption = caption.encode("UTF-8")
        if self.shorter_output:
            pcaption = "txt"
        else:
            pcaption = '[' + ((pcaption[:29] + u"\u2026") if len(pcaption) > 31 else pcaption) + ']'
        try:
            with open(filename, 'rb') as file:
                file_caption = file.read()
            if file_caption.replace(b'\r\n', b'\n') == caption.replace(b'\r\n', b'\n'):
                try:
                    self._log(pcaption + ' unchanged', end=' ', flush=True)
                except UnicodeEncodeError:
                    self._log('txt unchanged', end=' ', flush=True)
                return None
            else:
                def get_filename(index):
                    return filename if index == 0 else (filename[:-4] + '_old_' +
                                                        (str(0) if index < 10 else str()) + str(index) + filename[-4:])

                i = 0
                while os.path.isfile(get_filename(i)):
                    i = i + 1
                for index in range(i, 0, -1):
                    os.rename(get_filename(index - 1), get_filename(index))
                try:
                    self._log(pcaption + ' updated', end=' ', flush=True)
                except UnicodeEncodeError:
                    self._log('txt updated', end=' ', flush=True)
        except FileNotFoundError:
            pass
        try:
            self._log(pcaption, end=' ', flush=True)
        except UnicodeEncodeError:
            self._log('txt', end=' ', flush=True)
        with open(filename, 'wb') as text_file:
            shutil.copyfileobj(BytesIO(caption), text_file)
        os.utime(filename, (datetime.now().timestamp(), mtime.timestamp()))

    def save_location(self, filename: str, location_json: Dict[str, str], mtime: datetime) -> None:
        filename += '_location.txt'
        location_string = (location_json["name"] + "\n" +
                           "https://maps.google.com/maps?q={0},{1}&ll={0},{1}\n".format(location_json["lat"],
                                                                                        location_json["lng"]))
        with open(filename, 'wb') as text_file:
            shutil.copyfileobj(BytesIO(location_string.encode()), text_file)
        os.utime(filename, (datetime.now().timestamp(), mtime.timestamp()))
        self._log('geo', end=' ', flush=True)

    def download_profilepic(self, name: str, url: str) -> None:
        """Downloads and saves profile pic with given url."""

        def _epoch_to_string(epoch: datetime) -> str:
            return epoch.strftime('%Y-%m-%d_%H-%M-%S')

        date_object = datetime.strptime(requests.head(url).headers["Last-Modified"],
                                        '%a, %d %b %Y %H:%M:%S GMT')
        if ((format_string_contains_key(self.dirname_pattern, 'profile') or
             format_string_contains_key(self.dirname_pattern, 'target'))):
            filename = '{0}/{1}_UTC_profile_pic.{2}'.format(self.dirname_pattern.format(profile=name.lower(),
                                                                                        target=name.lower()),
                                                            _epoch_to_string(date_object), url[-3:])
        else:
            filename = '{0}/{1}_{2}_UTC_profile_pic.{3}'.format(self.dirname_pattern.format(), name.lower(),
                                                                _epoch_to_string(date_object), url[-3:])
        if os.path.isfile(filename):
            self._log(filename + ' already exists')
            return None
        match = re.search('http.*://.*instagram.*[^/]*\\.(com|net)/[^/]+/.', url)
        if match is None:
            raise ConnectionException("URL \'" + url + "\' could not be processed.")
        index = len(match.group(0)) - 1
        offset = 8 if match.group(0)[-1:] == 's' else 0
        url = url[:index] + 's2048x2048' + ('/' if offset == 0 else str()) + url[index + offset:]
        self._get_and_write_raw(url, filename)
        os.utime(filename, (datetime.now().timestamp(), date_object.timestamp()))

    def save_session_to_file(self, filename: Optional[str] = None) -> None:
        """Saves requests.Session object."""
        if filename is None:
            filename = get_default_session_filename(self.username)
        dirname = os.path.dirname(filename)
        if dirname != '' and not os.path.exists(dirname):
            os.makedirs(dirname)
            os.chmod(dirname, 0o700)
        with open(filename, 'wb') as sessionfile:
            os.chmod(filename, 0o600)
            pickle.dump(requests.utils.dict_from_cookiejar(self.session.cookies), sessionfile)
            self._log("Saved session to %s." % filename)

    def load_session_from_file(self, username: str, filename: Optional[str] = None) -> None:
        """Internally stores requests.Session object loaded from file.

        If filename is None, the file with the default session path is loaded.

        :raises FileNotFoundError; If the file does not exist.
        """
        if filename is None:
            filename = get_default_session_filename(username)
        with open(filename, 'rb') as sessionfile:
            session = requests.Session()
            session.cookies = requests.utils.cookiejar_from_dict(pickle.load(sessionfile))
            session.headers.update(self.default_http_header())
            session.headers.update({'X-CSRFToken': session.cookies.get_dict()['csrftoken']})
            self._log("Loaded session from %s." % filename)
            self.session = session
            self.username = username

    def test_login(self, session: requests.Session) -> Optional[str]:
        """Returns the Instagram username to which given requests.Session object belongs, or None."""
        if self.session is None:
            return
        data = self.get_json(str(), session=session)
        if data['config']['viewer'] is None:
            return
        return data['config']['viewer']['username']

    def login(self, user: str, passwd: str) -> None:
        """Log in to instagram with given username and password and internally store session object"""
        session = requests.Session()
        session.cookies.update({'sessionid': '', 'mid': '', 'ig_pr': '1',
                                'ig_vw': '1920', 'csrftoken': '',
                                's_network': '', 'ds_user_id': ''})
        session.headers.update(self.default_http_header())
        self._sleep()
        resp = session.get('https://www.instagram.com/')
        session.headers.update({'X-CSRFToken': resp.cookies['csrftoken']})
        self._sleep()
        login = session.post('https://www.instagram.com/accounts/login/ajax/',
                             data={'password': passwd, 'username': user}, allow_redirects=True)
        session.headers.update({'X-CSRFToken': login.cookies['csrftoken']})
        if login.status_code == 200:
            if user == self.test_login(session):
                self.username = user
                self.session = session
            else:
                raise BadCredentialsException('Login error! Check your credentials!')
        else:
            raise ConnectionException('Login error! Connection error!')

    def get_feed_json(self, end_cursor: str = None) -> Dict[str, Any]:
        """
        Get JSON of the user's feed.

        :param end_cursor: The end cursor, as from json["feed"]["media"]["page_info"]["end_cursor"]
        :return: JSON
        """
        if end_cursor is None:
            return self.get_json(str())["entry_data"]["FeedPage"][0]
        return self.graphql_query(17863003771166879, {'fetch_media_item_count': 12,
                                                      'fetch_media_item_cursor': end_cursor,
                                                      'fetch_comment_count': 4,
                                                      'fetch_like': 10})

    def get_node_metadata(self, node_code: str, tries: int = 3) -> Dict[str, Any]:
        pic_json = self.get_json("p/" + node_code)
        try:
            media = pic_json["entry_data"]["PostPage"][0]["graphql"]["shortcode_media"] \
                if "graphql" in pic_json["entry_data"]["PostPage"][0] \
                else pic_json["entry_data"]["PostPage"][0]["media"]
        except KeyError as err:
            print(err, file=sys.stderr)
            print(json.dumps(pic_json, indent=4), file=sys.stderr)
            if tries <= 1:
                raise NodeUnavailableException
            self._sleep()
            media = self.get_node_metadata(node_code, tries - 1)
        return media

    def get_location(self, node_code: str) -> Dict[str, str]:
        try:
            media = self.get_node_metadata(node_code)
        except NodeUnavailableException:
            print("Unable to lookup location for node \"https://www.instagram.com/p/{}/\".".format(node_code),
                  file=sys.stderr)
            return dict()
        if media["location"] is not None:
            location_json = self.get_json("explore/locations/" +
                                          media["location"]["id"])
            return location_json["entry_data"]["LocationsPage"][0]["location"]

    def download_node(self, node: Dict[str, Any], profile: Optional[str], target: str,
                      download_videos: bool = True, geotags: bool = False, download_comments: bool = False) -> bool:
        """
        Download everything associated with one instagram node, i.e. picture, caption and video.

        :param node: Node, as from media->nodes list in instagram's JSONs
        :param profile: Name of profile to which this node belongs
        :param target: Target name, i.e. profile name, #hashtag, :feed; for filename.
        :param download_videos: True, if videos should be downloaded
        :param geotags: Download geotags
        :param download_comments: Update comments
        :return: True if something was downloaded, False otherwise, i.e. file was already there
        """
        already_has_profilename = profile is not None or ('owner' in node and 'username' in node['owner'])
        needs_profilename = (format_string_contains_key(self.dirname_pattern, 'profile') or
                             format_string_contains_key(self.filename_pattern, 'profile'))
        shortcode = node['shortcode'] if 'shortcode' in node else node['code']
        if needs_profilename:
            if already_has_profilename:
                profilename = profile if profile is not None else node['owner']['username']
            else:
                try:
                    metadata = self.get_node_metadata(shortcode)
                    profilename = metadata['owner']['username']
                except NodeUnavailableException:
                    print("Unable to gather profilename for node "
                          "\"https://www.instagram.com/p/{}/\".".format(shortcode), file=sys.stderr)
                    profilename = 'UNKNOWN'
        else:
            profilename = None
        profilename = profilename.lower() if profilename else None
        date = datetime.fromtimestamp(node["date"] if "date" in node else node["taken_at_timestamp"])
        dirname = self.dirname_pattern.format(profile=profilename, target=target.lower())
        filename = dirname + '/' + self.filename_pattern.format(profile=profilename, target=target.lower(),
                                                                date=date,
                                                                shortcode=shortcode)
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        if '__typename' in node:
            if node['__typename'] == 'GraphSidecar':
                self._sleep()
                sidecar_data = self.session.get('https://www.instagram.com/p/' + shortcode + '/',
                                                params={'__a': 1}).json()
                edge_number = 1
                downloaded = True
                media = sidecar_data["graphql"]["shortcode_media"] if "graphql" in sidecar_data else sidecar_data[
                    "media"]
                for edge in media['edge_sidecar_to_children']['edges']:
                    edge_downloaded = self.download_pic(filename=filename,
                                                        url=edge['node']['display_url'],
                                                        mtime=date,
                                                        filename_suffix=str(edge_number))
                    downloaded = downloaded and edge_downloaded
                    edge_number += 1
            elif node['__typename'] in ['GraphImage', 'GraphVideo']:
                url = node["display_url"] if "display_url" in node else node["display_src"]
                downloaded = self.download_pic(filename=filename,
                                               url=url,
                                               mtime=date)
            else:
                self._log("Warning: Unknown typename discovered:" + node['__typename'])
                downloaded = False
        else:
            # Node is an old image or video.
            downloaded = self.download_pic(filename=filename, url=node["display_src"], mtime=date)
        if "edge_media_to_caption" in node and node["edge_media_to_caption"]["edges"]:
            self.save_caption(filename, date, node["edge_media_to_caption"]["edges"][0]["node"]["text"])
        elif "caption" in node:
            self.save_caption(filename, date, node["caption"])
        else:
            self._log("<no caption>", end=' ', flush=True)
        if node["is_video"] and download_videos:
            video_data = self.get_json('p/' + shortcode)
            self.download_pic(filename=filename,
                              url=video_data['entry_data']['PostPage'][0]['graphql']['shortcode_media']['video_url'],
                              mtime=date)
        if geotags:
            location = self.get_location(shortcode)
            if location:
                self.save_location(filename, location, date)
        if download_comments:
            self.update_comments(filename, shortcode)
        self._log()
        return downloaded

    def download_stories(self,
                         userids: Optional[List[int]] = None,
                         download_videos: bool = True,
                         fast_update: bool = False,
                         filename_target: str = ':stories') -> None:
        """
        Download available stories from user followees or all stories of users whose ID are given.
        Does not mark stories as seen.
        To use this, one needs to be logged in

        :param userids: List of user IDs to be processed in terms of downloading their stories
        :param download_videos: True, if videos should be downloaded
        :param fast_update: If true, abort when first already-downloaded picture is encountered
        :param filename_target: Replacement for {target} in dirname_pattern and filename_pattern
        """

        if self.username is None:
            raise LoginRequiredException('Login required to download stories')

        tempsession = copy_session(self.session)
        header = tempsession.headers
        header['User-Agent'] = 'Instagram 10.3.2 (iPhone7,2; iPhone OS 9_3_3; en_US; en-US; scale=2.00; 750x1334) ' \
                               'AppleWebKit/420+'
        del header['Host']
        del header['Origin']
        del header['X-Instagram-AJAX']
        del header['X-Requested-With']

        def _user_stories():
            def _get(url):
                self._sleep()
                resp = tempsession.get(url)
                if resp.status_code != 200:
                    raise ConnectionException('Failed to fetch stories.')
                return json.loads(resp.text)
            url_reel_media = 'https://i.instagram.com/api/v1/feed/user/{0}/reel_media/'
            url_reels_tray = 'https://i.instagram.com/api/v1/feed/reels_tray/'
            if userids is not None:
                for userid in userids:
                    yield _get(url_reel_media.format(userid))
            else:
                data = _get(url_reels_tray)
                if not 'tray' in data:
                    raise BadResponseException('Bad story reel JSON.')
                for user in data["tray"]:
                    yield user if "items" in user else _get(url_reel_media.format(user['user']['pk']))

        for user_stories in _user_stories():
            if "items" not in user_stories:
                continue
            name = user_stories["user"]["username"].lower()
            self._log("Retrieving stories from profile {}.".format(name))
            totalcount = len(user_stories["items"]) if "items" in user_stories else 0
            count = 1
            for item in user_stories["items"]:
                self._log("[%3i/%3i] " % (count, totalcount), end="", flush=True)
                count += 1

                self._sleep()
                shortcode = item["code"] if "code" in item else "no_code"

                date_float = item["device_timestamp"] if "device_timestamp" in item else item["taken_at"]
                try:
                    date = datetime.fromtimestamp(date_float)
                except ValueError:
                    # device_timestamp seems to sometime be in milliseconds
                    date_float /= 1000
                    date = datetime.fromtimestamp(date_float)

                dirname = self.dirname_pattern.format(profile=name, target=filename_target)
                filename = dirname + '/' + self.filename_pattern.format(profile=name, target=filename_target,
                                                                        date=date,
                                                                        shortcode=shortcode)
                os.makedirs(os.path.dirname(filename), exist_ok=True)
                try:
                    if "image_versions2" in item:
                        url = item["image_versions2"]["candidates"][0]["url"]
                        downloaded = self.download_pic(filename=filename,
                                                       url=url,
                                                       mtime=date)
                    else:
                        self._log("Warning: Unable to find story image.")
                        downloaded = False
                    if "caption" in item and item["caption"] is not None:
                        caption = item["caption"]
                        if isinstance(caption, dict) and "text" in caption:
                            caption = caption["text"]
                        self.save_caption(filename, date, caption)
                    else:
                        self._log("<no caption>", end=' ', flush=True)
                    if "video_versions" in item and download_videos:
                        downloaded = self.download_pic(filename=filename,
                                                       url=item["video_versions"][0]["url"],
                                                       mtime=date)
                        if "video_duration" in item and self.sleep and downloaded:
                            time.sleep(item["video_duration"])
                except NodeUnavailableException:
                    print("Unable to download node \"https://www.instagram.com/p/{}/\" of user {} from stories."
                          .format(shortcode, name), file=sys.stderr)
                    continue
                if item["story_locations"]:
                    location = item["story_locations"][0]["location"]
                    if location:
                        self.save_location(filename, location, date)
                self._log()
                if fast_update and not downloaded:
                    break

    def download_feed_pics(self, max_count: int = None, fast_update: bool = False,
                           filter_func: Optional[Callable[[Dict[str, Dict[str, Any]]], bool]] = None,
                           download_videos: bool = True, geotags: bool = False,
                           download_comments: bool = False) -> None:
        """
        Download pictures from the user's feed.

        Example to download up to the 20 pics the user last liked:
        >>> loader = Instaloader()
        >>> loader.load_session_from_file('USER')
        >>> loader.download_feed_pics(max_count=20, fast_update=True,
        >>>                           filter_func=lambda node:
        >>>                                       not node["likes"]["viewer_has_liked"]
        >>>                                       if "likes" in node else
        >>>                                       not node["viewer_has_liked"])

        :param max_count: Maximum count of pictures to download
        :param fast_update: If true, abort when first already-downloaded picture is encountered
        :param filter_func: function(node), which returns True if given picture should not be downloaded
        :param download_videos: True, if videos should be downloaded
        :param geotags: Download geotags
        :param download_comments: Update comments
        """
        data = self.get_feed_json()
        count = 1
        while True:
            if "graphql" in data:
                is_edge = True
                feed = data["graphql"]["user"]["edge_web_feed_timeline"]
            elif "data" in data:
                is_edge = True
                feed = data["data"]["user"]["edge_web_feed_timeline"]
            else:
                is_edge = False
                feed = data["feed"]["media"]
            for edge_or_node in feed["edges"] if is_edge else feed["nodes"]:
                if max_count is not None and count > max_count:
                    return
                node = edge_or_node["node"] if is_edge else edge_or_node
                name = node["owner"]["username"]
                if filter_func is not None and filter_func(node):
                    self._log("<pic by %s skipped>" % name, flush=True)
                    continue
                self._log("[%3i] %s " % (count, name), end="", flush=True)
                count += 1
                try:
                    downloaded = self.download_node(node, profile=name, target=':feed',
                                                    download_videos=download_videos, geotags=geotags,
                                                    download_comments=download_comments)
                except NodeUnavailableException:
                    print("Unable to download node \"https://www.instagram.com/p/{}/\" of user {} from feed."
                          .format(node['shortcode'], name), file=sys.stderr)
                    continue
                if fast_update and not downloaded:
                    return
            if not feed["page_info"]["has_next_page"]:
                break
            data = self.get_feed_json(end_cursor=feed["page_info"]["end_cursor"])

    def get_hashtag_json(self, hashtag: str,
                         max_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Return JSON of a #hashtag"""
        return self.get_json(name='explore/tags/{0}/'.format(hashtag), max_id=max_id)

    def download_hashtag(self, hashtag: str,
                         max_count: Optional[int] = None,
                         filter_func: Optional[Callable[[Dict[str, Dict[str, Any]]], bool]] = None,
                         fast_update: bool = False, download_videos: bool = True, geotags: bool = False,
                         download_comments: bool = False) -> None:
        """Download pictures of one hashtag.

        To download the last 30 pictures with hashtag #cat, do
        >>> loader = Instaloader()
        >>> loader.download_hashtag('cat', max_count=30)

        :param hashtag: Hashtag to download, without leading '#'
        :param max_count: Maximum count of pictures to download
        :param filter_func: function(node), which returns True if given picture should not be downloaded
        :param fast_update: If true, abort when first already-downloaded picture is encountered
        :param download_videos: True, if videos should be downloaded
        :param geotags: Download geotags
        :param download_comments: Update comments
        """
        data = self.get_hashtag_json(hashtag)
        count = 1
        while data:
            for node in data['entry_data']['TagPage'][0]['tag']['media']['nodes']:
                if max_count is not None and count > max_count:
                    return
                self._log('[{0:3d}] #{1} '.format(count, hashtag), end='', flush=True)
                if filter_func is not None and filter_func(node):
                    self._log('<skipped>')
                    continue
                count += 1
                try:
                    downloaded = self.download_node(node=node, profile=None, target='#'+hashtag,
                                                    download_videos=download_videos, geotags=geotags,
                                                    download_comments=download_comments)
                except NodeUnavailableException:
                    print("Unable to download node \"https://www.instagram.com/p/{}/\" "
                          "while downloading hashtag \"{}\".".format(node['shortcode'], hashtag), file=sys.stderr)
                    continue
                if fast_update and not downloaded:
                    return
            if data['entry_data']['TagPage'][0]['tag']['media']['page_info']['has_next_page']:
                data = self.get_hashtag_json(hashtag,
                                             max_id=data['entry_data']['TagPage'][0]['tag']['media']['page_info'][
                                                 'end_cursor'])
            else:
                break

    def check_id(self, profile: str, json_data: Dict[str, Any]) -> Tuple[str, int]:
        """
        Consult locally stored ID of profile with given name, check whether ID matches and whether name
        has changed and return current name of the profile, and store ID of profile.

        :return: current profile name, profile id
        """
        profile_exists = "ProfilePage" in json_data["entry_data"]
        if ((format_string_contains_key(self.dirname_pattern, 'profile') or
             format_string_contains_key(self.dirname_pattern, 'target'))):
            id_filename = '{0}/id'.format(self.dirname_pattern.format(profile=profile.lower(),
                                                                      target=profile.lower()))
        else:
            id_filename = '{0}/{1}_id'.format(self.dirname_pattern.format(), profile.lower())
        try:
            with open(id_filename, 'rb') as id_file:
                profile_id = int(id_file.read())
            if (not profile_exists) or \
                    (profile_id != int(json_data['entry_data']['ProfilePage'][0]['user']['id'])):
                if profile_exists:
                    self._log("Profile {0} does not match the stored unique ID {1}.".format(profile, profile_id))
                else:
                    self._log("Trying to find profile {0} using its unique ID {1}.".format(profile, profile_id))
                newname = self.get_username_by_id(profile_id)
                self._log("Profile {0} has changed its name to {1}.".format(profile, newname))
                if ((format_string_contains_key(self.dirname_pattern, 'profile') or
                     format_string_contains_key(self.dirname_pattern, 'target'))):
                    os.rename(self.dirname_pattern.format(profile=profile.lower(),
                                                          target=profile.lower()),
                              self.dirname_pattern.format(profile=newname.lower(),
                                                          target=newname.lower()))
                else:
                    os.rename('{0}/{1}_id'.format(self.dirname_pattern.format(), profile.lower()),
                              '{0}/{1}_id'.format(self.dirname_pattern.format(), newname.lower()))
                return newname, profile_id
            return profile, profile_id
        except FileNotFoundError:
            pass
        if profile_exists:
            os.makedirs(self.dirname_pattern.format(profile=profile.lower(),
                                                    target=profile.lower()), exist_ok=True)
            with open(id_filename, 'w') as text_file:
                profile_id = json_data['entry_data']['ProfilePage'][0]['user']['id']
                text_file.write(profile_id + "\n")
                self._log("Stored ID {0} for profile {1}.".format(profile_id, profile))
            return profile, profile_id
        raise ProfileNotExistsException("Profile {0} does not exist.".format(profile))

    def download(self, name: str,
                 profile_pic_only: bool = False, download_videos: bool = True, geotags: bool = False,
                 download_comments: bool = False, fast_update: bool = False,
                 download_stories: bool = False, download_stories_only: bool = False) -> None:
        """Download one profile"""
        # Get profile main page json
        data = self.get_json(name)
        # check if profile does exist or name has changed since last download
        # and update name and json data if necessary
        name_updated, profile_id = self.check_id(name, data)
        if name_updated != name:
            name = name_updated
            data = self.get_json(name)
        # Download profile picture
        try:
            self.download_profilepic(name, data["entry_data"]["ProfilePage"][0]["user"]["profile_pic_url"])
        except NodeUnavailableException:
            print("Unable to download profilepic of user {}.".format(name), file=sys.stderr)
        if profile_pic_only:
            return
        # Catch some errors
        if data["entry_data"]["ProfilePage"][0]["user"]["is_private"]:
            if data["config"]["viewer"] is None:
                raise LoginRequiredException("profile %s requires login" % name)
            if not data["entry_data"]["ProfilePage"][0]["user"]["followed_by_viewer"] and \
                    self.username != data["entry_data"]["ProfilePage"][0]["user"]["username"]:
                raise PrivateProfileNotFollowedException("Profile %s: private but not followed." % name)
        else:
            if data["config"]["viewer"] is not None and not (download_stories or download_stories_only):
                self._log("profile %s could also be downloaded anonymously." % name)
        if download_stories or download_stories_only:
            self.download_stories(userids=[profile_id], filename_target=name,
                                  download_videos=download_videos, fast_update=fast_update)
        if download_stories_only:
            return
        if ("nodes" not in data["entry_data"]["ProfilePage"][0]["user"]["media"] or
                not data["entry_data"]["ProfilePage"][0]["user"]["media"]["nodes"]) \
                and not profile_pic_only:
            raise ProfileHasNoPicsException("Profile %s: no pics found." % name)

        # Iterate over pictures and download them
        self._log("Retrieving posts from profile {}.".format(name))
        def get_last_id(data):
            if data["entry_data"] and data["entry_data"]["ProfilePage"][0]["user"]["media"]["nodes"]:
                return data["entry_data"]["ProfilePage"][0]["user"]["media"]["nodes"][-1]["id"]

        totalcount = data["entry_data"]["ProfilePage"][0]["user"]["media"]["count"]
        count = 1
        while get_last_id(data) is not None:
            for node in data["entry_data"]["ProfilePage"][0]["user"]["media"]["nodes"]:
                self._log("[%3i/%3i] " % (count, totalcount), end="", flush=True)
                count += 1
                try:
                    downloaded = self.download_node(node=node, profile=name, target=name,
                                                    download_videos=download_videos, geotags=geotags,
                                                    download_comments=download_comments)
                except NodeUnavailableException:
                    print("Unable to download node \"https://www.instagram.com/p/{}/\" of user {}."
                          .format(node['shortcode'], name), file=sys.stderr)
                    continue
                if fast_update and not downloaded:
                    return
            data = self.get_json(name, max_id=get_last_id(data))

    def interactive_login(self, username: str) -> None:
        """Logs in and internally stores session, asking user for password interactively.

        :raises LoginRequiredException: when in quiet mode."""
        if self.quiet:
            raise LoginRequiredException("Quiet mode requires given password or valid session file.")
        password = None
        while password is None:
            password = getpass.getpass(prompt="Enter Instagram password for %s: " % username)
            try:
                self.login(username, password)
            except BadCredentialsException as err:
                print(err, file=sys.stderr)
                password = None

    def download_profiles(self, profilelist: List[str], username: Optional[str] = None, password: Optional[str] = None,
                          sessionfile: Optional[str] = None, max_count: Optional[int] = None,
                          profile_pic_only: bool = False, download_videos: bool = True, geotags: bool = False,
                          download_comments: bool = False,
                          fast_update: bool = False,
                          stories: bool = False, stories_only: bool = False) -> None:
        """Download set of profiles and handle sessions"""
        # Login, if desired
        if username is not None:
            try:
                self.load_session_from_file(username, sessionfile)
            except FileNotFoundError as err:
                if sessionfile is not None:
                    print(err, file=sys.stderr)
                self._log("Session file does not exist yet - Logging in.")
            if username != self.test_login(self.session):
                if password is not None:
                    self.login(username, password)
                else:
                    self.interactive_login(username)
            self._log("Logged in as %s." % username)
        # Try block for KeyboardInterrupt (save session on ^C)
        failedtargets = []
        targets = set()
        try:
            # Generate set of targets
            for pentry in profilelist:
                if pentry[0] == '#':
                    self._log("Retrieving pictures with hashtag {0}".format(pentry))
                    self.download_hashtag(hashtag=pentry[1:], max_count=max_count, fast_update=fast_update,
                                          download_videos=download_videos, geotags=geotags,
                                          download_comments=download_comments)
                elif pentry[0] == '@':
                    if username is not None:
                        self._log("Retrieving followees of %s..." % pentry[1:])
                        followees = self.get_followees(pentry[1:])
                        targets.update([followee['username'] for followee in followees])
                    else:
                        print("--login=USERNAME required to download {}.".format(pentry), file=sys.stderr)
                elif pentry == ":feed-all":
                    if username is not None:
                        self._log("Retrieving pictures from your feed...")
                        self.download_feed_pics(fast_update=fast_update, max_count=max_count,
                                                download_videos=download_videos, geotags=geotags,
                                                download_comments=download_comments)
                    else:
                        print("--login=USERNAME required to download {}.".format(pentry), file=sys.stderr)
                elif pentry == ":feed-liked":
                    if username is not None:
                        self._log("Retrieving pictures you liked from your feed...")
                        self.download_feed_pics(fast_update=fast_update, max_count=max_count,
                                                filter_func=lambda node:
                                                not node["likes"]["viewer_has_liked"]
                                                if "likes" in node
                                                else not node["viewer_has_liked"],
                                                download_videos=download_videos, geotags=geotags,
                                                download_comments=download_comments)
                    else:
                        print("--login=USERNAME required to download {}.".format(pentry), file=sys.stderr)
                elif pentry == ":stories":
                    if username is not None:
                        self.download_stories(download_videos=download_videos, fast_update=fast_update)
                    else:
                        print("--login=USERNAME required to download {}.".format(pentry), file=sys.stderr)
                else:
                    targets.add(pentry)
            if len(targets) > 1:
                self._log("Downloading %i profiles..." % len(targets))
            # Iterate through targets list and download them
            for target in targets:
                try:
                    try:
                        self.download(target, profile_pic_only, download_videos,
                                      geotags, download_comments, fast_update, stories, stories_only)
                    except ProfileNotExistsException as err:
                        if username is not None:
                            self._log(err)
                            self._log("Trying again anonymously, helps in case you are just blocked.")
                            anonymous_loader = Instaloader(self.sleep, self.quiet, self.shorter_output,
                                                           self.user_agent, self.dirname_pattern, self.filename_pattern)
                            anonymous_loader.download(target, profile_pic_only, download_videos,
                                                      geotags, download_comments, fast_update)
                        else:
                            raise err
                except NonfatalException as err:
                    failedtargets.append(target)
                    print(err, file=sys.stderr)
        except KeyboardInterrupt:
            print("\nInterrupted by user.", file=sys.stderr)
        if len(targets) > 1 and failedtargets:
            print("Errors occured (see above) while downloading profiles: %s." %
                  ", ".join(failedtargets), file=sys.stderr)
        # Save session if it is useful
        if username is not None:
            self.save_session_to_file(sessionfile)


def main():
    parser = ArgumentParser(description=__doc__, add_help=False,
                            epilog="Report issues at https://github.com/Thammus/instaloader/issues.")

    g_what = parser.add_argument_group('What to Download',
                                       'Specify a list of profiles or #hashtags. For each of these, Instaloader '
                                       'creates a folder and '
                                       'downloads all posts along with the pictures\'s '
                                       'captions and the current profile picture. '
                                       'If an already-downloaded profile has been renamed, Instaloader automatically '
                                       'finds it by its unique ID and renames the folder likewise.')
    g_what.add_argument('profile', nargs='*', metavar='profile|#hashtag',
                        help='Name of profile or #hashtag to download. '
                             'Alternatively, if --login is given: @<profile> to download all followees of '
                             '<profile>; the special targets :feed-all or :feed-liked to '
                             'download pictures from your feed; or :stories to download the stories of your '
                             'followees.')
    g_what.add_argument('-P', '--profile-pic-only', action='store_true',
                        help='Only download profile picture.')
    g_what.add_argument('-V', '--skip-videos', action='store_true',
                        help='Do not download videos.')
    g_what.add_argument('-G', '--geotags', action='store_true',
                        help='Download geotags when available. Geotags are stored as a '
                             'text file with the location\'s name and a Google Maps link. '
                             'This requires an additional request to the Instagram '
                             'server for each picture, which is why it is disabled by default.')
    g_what.add_argument('-C', '--comments', action='store_true',
                        help='Download and update comments for each post. '
                             'This requires an additional request to the Instagram '
                             'server for each post, which is why it is disabled by default.')
    g_what.add_argument('-s', '--stories', action='store_true',
                        help='Also download stories of each profile that is downloaded. Requires --login.')
    g_what.add_argument('--stories-only', action='store_true',
                        help='Rather than downloading regular posts of each specified profile, only download '
                             'stories. Requires --login.')

    g_stop = parser.add_argument_group('When to Stop Downloading',
                                       'If none of these options are given, Instaloader goes through all pictures '
                                       'matching the specified targets.')
    g_stop.add_argument('-F', '--fast-update', action='store_true',
                        help='For each target, stop when encountering the first already-downloaded picture. This '
                             'flag is recommended when you use Instaloader to update your personal Instagram archive.')
    g_stop.add_argument('-c', '--count',
                        help='Do not attempt to download more than COUNT posts. '
                             'Applies only to #hashtag, :feed-all and :feed-liked.')

    g_login = parser.add_argument_group('Login (Download Private Profiles)',
                                        'Instaloader can login to Instagram. This allows downloading private profiles. '
                                        'To login, pass the --login option. Your session cookie (not your password!) '
                                        'will be saved to a local file to be reused next time you want Instaloader '
                                        'to login.')
    g_login.add_argument('-l', '--login', metavar='YOUR-USERNAME',
                         help='Login name (profile name) for your Instagram account.')
    g_login.add_argument('-f', '--sessionfile',
                         help='Path for loading and storing session key file. '
                              'Defaults to ' + get_default_session_filename("<login_name>"))
    g_login.add_argument('-p', '--password', metavar='YOUR-PASSWORD',
                         help='Password for your Instagram account. Without this option, '
                              'you\'ll be prompted for your password interactively if '
                              'there is not yet a valid session file.')

    g_how = parser.add_argument_group('How to Download')
    g_how.add_argument('--dirname-pattern',
                       help='Name of directory where to store posts. {profile} is replaced by the profile name, '
                            '{target} is replaced by the target you specified, i.e. either :feed, #hashtag or the '
                            'profile name. Defaults to \'{target}\'.')
    g_how.add_argument('--filename-pattern',
                       help='Prefix of filenames. Posts are stored in the directory whose pattern is given with '
                            '--dirname-pattern. {profile} is replaced by the profile name, '
                            '{target} is replaced by the target you specified, i.e. either :feed, #hashtag or the '
                            'profile name. Also, the fields date and shortcode can be specified. Defaults to '
                            '\'{date:%%Y-%%m-%%d_%%H-%%M-%%S}\'.')
    g_how.add_argument('--user-agent',
                       help='User Agent to use for HTTP requests. Defaults to \'{}\'.'.format(default_user_agent()))
    g_how.add_argument('-S', '--no-sleep', action='store_true',
                       help='Do not sleep between requests to Instagram\'s servers. This makes downloading faster, but '
                            'may be suspicious.')

    g_misc = parser.add_argument_group('Miscellaneous Options')
    g_misc.add_argument('-O', '--shorter-output', action='store_true',
                        help='Do not display captions while downloading.')
    g_misc.add_argument('-q', '--quiet', action='store_true',
                        help='Disable user interaction, i.e. do not print messages (except errors) and fail '
                             'if login credentials are needed but not given. This makes Instaloader suitable as a '
                             'cron job.')
    g_misc.add_argument('-h', '--help', action='help', help='Show this help message and exit.')
    g_misc.add_argument('--version', action='version', help='Show version number and exit.',
                        version=__version__)

    args = parser.parse_args()
    try:
        if args.login is None and (args.stories or args.stories_only):
            print("--login=USERNAME required to download stories.", file=sys.stderr)
            args.stories = False
            if args.stories_only:
                raise SystemExit(1)
        loader = Instaloader(sleep=not args.no_sleep, quiet=args.quiet, shorter_output=args.shorter_output,
                             user_agent=args.user_agent,
                             dirname_pattern=args.dirname_pattern, filename_pattern=args.filename_pattern)
        loader.download_profiles(args.profile, args.login.lower() if args.login is not None else None, args.password,
                                 args.sessionfile,
                                 int(args.count) if args.count is not None else None,
                                 args.profile_pic_only, not args.skip_videos, args.geotags, args.comments,
                                 args.fast_update, args.stories, args.stories_only)
    except InstaloaderException as err:
        raise SystemExit("Fatal error: %s" % err)


if __name__ == "__main__":
    main()
