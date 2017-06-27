#!/usr/bin/env python3

"""Tool to download pictures (or videos) and captions from Instagram, from a given set
of profiles (even if private), from your feed or from all followees of a given profile."""

import datetime
import getpass
import json
import os
import pickle
import random
import re
import shutil
import sys
import tempfile
import time
from argparse import ArgumentParser
from io import BytesIO
from typing import Any, Callable, Dict, List, Optional

import requests
import requests.utils


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


class BadCredentialsException(InstaloaderException):
    pass


class ConnectionException(InstaloaderException):
    pass


def _epoch_to_string(epoch: float) -> str:
    return datetime.datetime.fromtimestamp(epoch).strftime('%Y-%m-%d_%H-%M-%S')


def get_default_session_filename(username: str) -> str:
    """Returns default session filename for given username."""
    dirname = tempfile.gettempdir() + "/" + ".instaloader-" + getpass.getuser()
    filename = dirname + "/" + "session-" + username
    return filename


def copy_session(session: requests.Session) -> requests.Session:
    """Duplicates a requests.Session."""
    new = requests.Session()
    new.cookies = \
        requests.utils.cookiejar_from_dict(requests.utils.dict_from_cookiejar(session.cookies))
    new.headers = session.headers
    return new


def default_http_header(empty_session_only: bool = False) -> Dict[str, str]:
    """Returns default HTTP header we use for requests."""
    user_agent = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 ' \
                 '(KHTML, like Gecko) Chrome/51.0.2704.79 Safari/537.36'
    header = {'Accept-Encoding': 'gzip, deflate',
              'Accept-Language': 'en-US,en;q=0.8',
              'Connection': 'keep-alive',
              'Content-Length': '0',
              'Host': 'www.instagram.com',
              'Origin': 'https://www.instagram.com',
              'Referer': 'https://www.instagram.com/',
              'User-Agent': user_agent,
              'X-Instagram-AJAX': '1',
              'X-Requested-With': 'XMLHttpRequest'}
    if empty_session_only:
        del header['Host']
        del header['Origin']
        del header['Referer']
        del header['X-Instagram-AJAX']
        del header['X-Requested-With']
    return header


def get_anonymous_session() -> requests.Session:
    """Returns our default anonymous requests.Session object."""
    session = requests.Session()
    session.cookies.update({'sessionid': '', 'mid': '', 'ig_pr': '1',
                            'ig_vw': '1920', 'csrftoken': '',
                            's_network': '', 'ds_user_id': ''})
    session.headers.update(default_http_header(empty_session_only=True))
    return session


class Instaloader:
    def __init__(self,
                 sleep: bool = True, quiet: bool = False, shorter_output: bool = False, profile_subdirs: bool = True):
        self.session = get_anonymous_session()
        self.username = None
        self.sleep = sleep
        self.quiet = quiet
        self.shorter_output = shorter_output
        self.profile_subdirs = profile_subdirs

    def _log(self, *msg, sep='', end='\n', flush=False):
        if not self.quiet:
            print(*msg, sep=sep, end=end, flush=flush)

    def get_json(self, name: str, session: requests.Session = None,
                 max_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Return JSON of a profile"""
        if session is None:
            session = self.session
        if not max_id:
            resp = session.get('https://www.instagram.com/' + name)
        else:
            resp = session.get('https://www.instagram.com/' + name, params={'max_id': max_id})
        if self.sleep:
            time.sleep(4 * random.random() + 1)
        match = re.search('window\\._sharedData = .*<', resp.text)
        if match is not None:
            return json.loads(match.group(0)[21:-2])

    def get_username_by_id(self, profile_id: int) -> str:
        """To get the current username of a profile, given its unique ID, this function can be used.
        session is required to be a logged-in (i.e. non-anonymous) session."""
        tempsession = copy_session(self.session)
        tempsession.headers.update({'Content-Type': 'application/x-www-form-urlencoded'})
        resp = tempsession.post('https://www.instagram.com/query/',
                                data='q=ig_user(' + str(profile_id) + ')+%7B%0A++username%0A%7D%0A')
        if resp.status_code == 200:
            data = json.loads(resp.text)
            if 'username' in data:
                return json.loads(resp.text)['username']
            raise ProfileNotExistsException("No profile found, the user may have blocked " +
                                            "you (id: " + str(profile_id) + ").")
        else:
            if self.test_login(self.session):
                raise ProfileAccessDeniedException("Username could not be determined due to error {0} (id: {1})."
                                                   .format(str(resp.status_code), str(profile_id)))
            raise LoginRequiredException("Login required to determine username (id: " +
                                         str(profile_id) + ").")

    def get_id_by_username(self, profile: str) -> int:
        """Each Instagram profile has its own unique ID which stays unmodified even if a user changes
        his/her username. To get said ID, given the profile's name, you may call this function."""
        data = self.get_json(profile, session=get_anonymous_session())
        if "ProfilePage" not in data["entry_data"]:
            raise ProfileNotExistsException("Profile {0} does not exist.".format(profile))
        return int(data['entry_data']['ProfilePage'][0]['user']['id'])

    def get_followees(self, profile: str) -> List[Dict[str, Any]]:
        """
        Retrieve list of followees of given profile

        :param profile: Name of profile to lookup followees
        :return: List of followees (list of dictionaries), as returned by instagram server
        """
        tmpsession = copy_session(self.session)
        data = self.get_json(profile, session=tmpsession)
        profile_id = data['entry_data']['ProfilePage'][0]['user']['id']
        query = ["q=ig_user(" + profile_id + ")+%7B%0A"
                                             "++follows.",
                 str(data['entry_data']['ProfilePage'][0]['user']['follows']['count']) +
                 ")+%7B%0A"
                 "++++count%2C%0A"
                 "++++page_info+%7B%0A"
                 "++++++end_cursor%2C%0A"
                 "++++++has_next_page%0A"
                 "++++%7D%2C%0A"
                 "++++nodes+%7B%0A"
                 "++++++id%2C%0A"
                 "++++++full_name%2C%0A"
                 "++++++username%2C%0A"
                 "++++++followed_by+%7B%0A"
                 "++++++++count%0A"
                 "++++++%7D%0A"
                 "++++%7D%0A"
                 "++%7D%0A"
                 "%7D%0A"
                 "&ref=relationships%3A%3Afollow_list"]
        tmpsession.headers.update(default_http_header())
        tmpsession.headers.update({'Referer': 'https://www.instagram.com/' + profile + '/following/'})
        tmpsession.headers.update({'Content-Type': 'application/x-www-form-urlencoded'})
        resp = tmpsession.post('https://www.instagram.com/query/', data=query[0] + "first(" + query[1])
        if resp.status_code == 200:
            data = json.loads(resp.text)
            followees = []
            while True:
                for followee in data['follows']['nodes']:
                    followee['follower_count'] = followee.pop('followed_by')['count']
                    followees = followees + [followee]
                if data['follows']['page_info']['has_next_page']:
                    resp = tmpsession.post('https://www.instagram.com/query/',
                                           data="{0}after({1}%2C+{2}".format(query[0],
                                                                             data['follows']['page_info']['end_cursor'],
                                                                             query[1]))
                    data = json.loads(resp.text)
                else:
                    break
            return followees
        if self.test_login(tmpsession):
            raise ConnectionException("ConnectionError(" + str(resp.status_code) + "): "
                                                                                   "unable to gather followees.")
        raise LoginRequiredException("Login required to gather followees.")

    def download_pic(self, name: str, url: str, date_epoch: float, outputlabel: Optional[str] = None,
                     filename_suffix: Optional[str] = None) -> bool:
        """Downloads and saves picture with given url under given directory with given timestamp.
        Returns true, if file was actually downloaded, i.e. updated."""
        if outputlabel is None:
            outputlabel = _epoch_to_string(date_epoch)
        urlmatch = re.search('\\.[a-z]*\\?', url)
        file_extension = url[-3:] if urlmatch is None else urlmatch.group(0)[1:-1]
        if self.profile_subdirs:
            filename = name.lower() + '/' + _epoch_to_string(date_epoch)
        else:
            filename = name.lower() + '__' + _epoch_to_string(date_epoch)
        if filename_suffix is not None:
            filename += '_' + filename_suffix
        filename += '.' + file_extension
        if os.path.isfile(filename):
            self._log(outputlabel + ' exists', end=' ', flush=True)
            return False
        resp = get_anonymous_session().get(url, stream=True)
        if resp.status_code == 200:
            self._log(outputlabel, end=' ', flush=True)
            if self.profile_subdirs:
                os.makedirs(name.lower(), exist_ok=True)
            with open(filename, 'wb') as file:
                resp.raw.decode_content = True
                shutil.copyfileobj(resp.raw, file)
            os.utime(filename, (datetime.datetime.now().timestamp(), date_epoch))
            return True
        else:
            raise ConnectionException("File \'" + url + "\' could not be downloaded.")

    def save_caption(self, name: str, date_epoch: float, caption: str) -> None:
        """Updates picture caption"""
        # pylint:disable=too-many-branches
        if self.profile_subdirs:
            filename = name.lower() + '/' + _epoch_to_string(date_epoch) + '.txt'
        else:
            filename = name.lower() + '__' + _epoch_to_string(date_epoch) + '.txt'
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
        if self.profile_subdirs:
            os.makedirs(name.lower(), exist_ok=True)
        with open(filename, 'wb') as text_file:
            shutil.copyfileobj(BytesIO(caption), text_file)
        os.utime(filename, (datetime.datetime.now().timestamp(), date_epoch))

    def save_location(self, name: str, location_json: Dict[str, str], date_epoch: float) -> None:
        if self.profile_subdirs:
            filename = name.lower() + '/' + _epoch_to_string(date_epoch) + '_location.txt'
        else:
            filename = name.lower() + '__' + _epoch_to_string(date_epoch) + '_location.txt'
        location_string = (location_json["name"] + "\n" +
                           "https://maps.google.com/maps?q={0},{1}&ll={0},{1}\n".format(location_json["lat"],
                                                                                        location_json["lng"]))
        if self.profile_subdirs:
            os.makedirs(name.lower(), exist_ok=True)
        with open(filename, 'wb') as text_file:
            shutil.copyfileobj(BytesIO(location_string.encode()), text_file)
        os.utime(filename, (datetime.datetime.now().timestamp(), date_epoch))
        self._log('geo', end=' ', flush=True)

    def download_profilepic(self, name: str, url: str) -> None:
        """Downloads and saves profile pic with given url."""
        date_object = datetime.datetime.strptime(requests.head(url).headers["Last-Modified"],
                                                 '%a, %d %b %Y %H:%M:%S GMT')
        if self.profile_subdirs:
            filename = name.lower() + '/' + _epoch_to_string(date_object.timestamp()) + '_UTC_profile_pic.' + url[-3:]
        else:
            filename = name.lower() + '__' + _epoch_to_string(date_object.timestamp()) + '_UTC_profile_pic.' + url[-3:]
        if os.path.isfile(filename):
            self._log(filename + ' already exists')
            return None
        match = re.search('http.*://.*instagram.*[^/]*\\.(com|net)/[^/]+/.', url)
        if match is None:
            raise ConnectionException("URL \'" + url + "\' could not be processed.")
        index = len(match.group(0)) - 1
        offset = 8 if match.group(0)[-1:] == 's' else 0
        url = url[:index] + 's2048x2048' + ('/' if offset == 0 else str()) + url[index + offset:]
        resp = get_anonymous_session().get(url, stream=True)
        if resp.status_code == 200:
            self._log(filename)
            if self.profile_subdirs:
                os.makedirs(name.lower(), exist_ok=True)
            with open(filename, 'wb') as file:
                resp.raw.decode_content = True
                shutil.copyfileobj(resp.raw, file)
            os.utime(filename, (datetime.datetime.now().timestamp(), date_object.timestamp()))
        else:
            raise ConnectionException("File \'" + url + "\' could not be downloaded.")

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
        """Returns loaded requests.Session object, or None if not found."""
        self.username = username
        if filename is None:
            filename = get_default_session_filename(username)
        with open(filename, 'rb') as sessionfile:
            session = requests.Session()
            session.cookies = requests.utils.cookiejar_from_dict(pickle.load(sessionfile))
            session.headers.update(default_http_header())
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
        time.sleep(4 * random.random() + 1)
        return data['config']['viewer']['username']

    def login(self, user: str, passwd: str) -> None:
        """Log in to instagram with given username and password and return session object"""
        session = requests.Session()
        session.cookies.update({'sessionid': '', 'mid': '', 'ig_pr': '1',
                                'ig_vw': '1920', 'csrftoken': '',
                                's_network': '', 'ds_user_id': ''})
        session.headers.update(default_http_header())
        resp = session.get('https://www.instagram.com/')
        session.headers.update({'X-CSRFToken': resp.cookies['csrftoken']})
        time.sleep(9 * random.random() + 3)
        login = session.post('https://www.instagram.com/accounts/login/ajax/',
                             data={'password': passwd, 'username': user}, allow_redirects=True)
        session.headers.update({'X-CSRFToken': login.cookies['csrftoken']})
        time.sleep(5 * random.random())
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
        tmpsession = copy_session(self.session)
        query = "q=ig_me()+%7B%0A++feed+%7B%0A++++media.after(" + end_cursor + "%2C+12)+%7B%0A" + \
                "++++++nodes+%7B%0A++++++++id%2C%0A++++++++caption%2C%0A++++++++code%2C%0A++++++++" + \
                "comments.last(4)+%7B%0A++++++++++count%2C%0A++++++++++nodes+%7B%0A++++++++++++" + \
                "id%2C%0A++++++++++++created_at%2C%0A++++++++++++text%2C%0A++++++++++++" + \
                "user+%7B%0A++++++++++++++id%2C%0A++++++++++++++profile_pic_url%2C%0A++++++++++++++" + \
                "username%0A++++++++++++%7D%0A++++++++++%7D%2C%0A++++++++++" + \
                "page_info%0A++++++++%7D%2C%0A++++++++comments_disabled%2C%0A++++++++" + \
                "date%2C%0A++++++++dimensions+%7B%0A++++++++++height%2C%0A++++++++++" + \
                "width%0A++++++++%7D%2C%0A++++++++display_src%2C%0A++++++++is_video%2C%0A++++++++" + \
                "likes+%7B%0A++++++++++count%2C%0A++++++++++nodes+%7B%0A++++++++++++" + \
                "user+%7B%0A++++++++++++++id%2C%0A++++++++++++++profile_pic_url%2C%0A++++++++++++++" + \
                "username%0A++++++++++++%7D%0A++++++++++%7D%2C%0A++++++++++" + \
                "viewer_has_liked%0A++++++++%7D%2C%0A++++++++location+%7B%0A++++++++++" + \
                "id%2C%0A++++++++++has_public_page%2C%0A++++++++++name%0A++++++++%7D%2C%0A++++++++" + \
                "owner+%7B%0A++++++++++id%2C%0A++++++++++blocked_by_viewer%2C%0A++++++++++" + \
                "followed_by_viewer%2C%0A++++++++++full_name%2C%0A++++++++++" + \
                "has_blocked_viewer%2C%0A++++++++++is_private%2C%0A++++++++++" + \
                "profile_pic_url%2C%0A++++++++++requested_by_viewer%2C%0A++++++++++" + \
                "username%0A++++++++%7D%2C%0A++++++++usertags+%7B%0A++++++++++" + \
                "nodes+%7B%0A++++++++++++user+%7B%0A++++++++++++++" + \
                "username%0A++++++++++++%7D%2C%0A++++++++++++x%2C%0A++++++++++++y%0A++++++++++" + \
                "%7D%0A++++++++%7D%2C%0A++++++++video_url%2C%0A++++++++" + \
                "video_views%0A++++++%7D%2C%0A++++++page_info%0A++++%7D%0A++%7D%2C%0A++id%2C%0A++" + \
                "profile_pic_url%2C%0A++username%0A%7D%0A&ref=feed::show"
        tmpsession.headers.update(default_http_header())
        tmpsession.headers.update({'Referer': 'https://www.instagram.com/'})
        tmpsession.headers.update({'Content-Type': 'application/x-www-form-urlencoded'})
        resp = tmpsession.post('https://www.instagram.com/query/', data=query)
        if self.sleep:
            time.sleep(4 * random.random() + 1)
        return json.loads(resp.text)

    def get_node_metadata(self, node_code: str) -> Dict[str, Any]:
        pic_json = self.get_json("p/" + node_code)
        media = pic_json["entry_data"]["PostPage"][0]["graphql"]["shortcode_media"] \
            if "graphql" in pic_json["entry_data"]["PostPage"][0] \
            else pic_json["entry_data"]["PostPage"][0]["media"]
        return media

    def get_location(self, node_code: str) -> Dict[str, str]:
        media = self.get_node_metadata(node_code)
        if media["location"] is not None:
            location_json = self.get_json("explore/locations/" +
                                          media["location"]["id"])
            return location_json["entry_data"]["LocationsPage"][0]["location"]

    def download_node(self, node: Dict[str, Any], name: str,
                      download_videos: bool = True, geotags: bool = False) -> bool:
        """
        Download everything associated with one instagram node, i.e. picture, caption and video.

        :param node: Node, as from media->nodes list in instagram's JSONs
        :param name: Name of profile to which this node belongs
        :param download_videos: True, if videos should be downloaded
        :param geotags: Download geotags
        :return: True if something was downloaded, False otherwise, i.e. file was already there
        """
        # pylint:disable=too-many-branches,too-many-locals
        date = node["date"] if "date" in node else node["taken_at_timestamp"]
        if '__typename' in node:
            if node['__typename'] == 'GraphSidecar':
                sidecar_data = self.session.get('https://www.instagram.com/p/' + node['code'] + '/',
                                                params={'__a': 1}).json()
                edge_number = 1
                downloaded = True
                media = sidecar_data["graphql"]["shortcode_media"] if "graphql" in sidecar_data else sidecar_data[
                    "media"]
                for edge in media['edge_sidecar_to_children']['edges']:
                    edge_downloaded = self.download_pic(name, edge['node']['display_url'], date,
                                                        filename_suffix=str(edge_number),
                                                        outputlabel=(str(edge_number) if edge_number != 1 else None))
                    downloaded = downloaded and edge_downloaded
                    edge_number += 1
                    if self.sleep:
                        time.sleep(1.75 * random.random() + 0.25)
            elif node['__typename'] in ['GraphImage', 'GraphVideo']:
                downloaded = self.download_pic(name,
                                               node["display_url"] if "display_url" in node else node["display_src"],
                                               date)
                if self.sleep:
                    time.sleep(1.75 * random.random() + 0.25)
            else:
                self._log("Warning: Unknown typename discovered:" + node['__typename'])
                downloaded = False
        else:
            # Node is an old image or video.
            downloaded = self.download_pic(name, node["display_src"], date)
            if self.sleep:
                time.sleep(1.75 * random.random() + 0.25)
        if "edge_media_to_caption" in node and node["edge_media_to_caption"]["edges"]:
            self.save_caption(name, date, node["edge_media_to_caption"]["edges"][0]["node"]["text"])
        elif "caption" in node:
            self.save_caption(name, date, node["caption"])
        else:
            self._log("<no caption>", end=' ', flush=True)
        node_code = node['shortcode'] if 'shortcode' in node else node['code']
        if node["is_video"] and download_videos:
            video_data = self.get_json('p/' + node_code)
            self.download_pic(name,
                              video_data['entry_data']['PostPage'][0]['graphql']['shortcode_media']['video_url'],
                              date, 'mp4')
        if geotags:
            location = self.get_location(node_code)
            if location:
                self.save_location(name, location, date)
        self._log()
        return downloaded

    def download_feed_pics(self, max_count: int = None, fast_update: bool = False,
                           filter_func: Optional[Callable[[Dict[str, Dict[str, Any]]], bool]] = None,
                           download_videos: bool = True, geotags: bool = False) -> None:
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
        """
        # pylint:disable=too-many-locals
        data = self.get_feed_json()
        count = 1
        while True:
            if "graphql" in data:
                is_edge = True
                feed = data["graphql"]["user"]["edge_web_feed_timeline"]
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
                downloaded = self.download_node(node, name,
                                                download_videos=download_videos, geotags=geotags)
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
                         lookup_username: bool = False) -> None:
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
        :param lookup_username: Lookup username to encode it in the downloaded file's path, rather than the hashtag
        """
        data = self.get_hashtag_json(hashtag)
        count = 1
        while data:
            for node in data['entry_data']['TagPage'][0]['tag']['media']['nodes']:
                if max_count is not None and count > max_count:
                    return
                if lookup_username:
                    metadata = self.get_node_metadata(node['shortcode'] if 'shortcode' in node else node['code'])
                    pathname = metadata['owner']['username']
                else:
                    pathname = '#{0}'.format(hashtag)
                self._log('[{0:3d}] #{1} {2}/'.format(count, hashtag, pathname), end='', flush=True)
                if filter_func is not None and filter_func(node):
                    self._log('<skipped>')
                    continue
                count += 1
                downloaded = self.download_node(node, pathname,
                                                download_videos=download_videos, geotags=geotags)
                if fast_update and not downloaded:
                    return
            if data['entry_data']['TagPage'][0]['tag']['media']['page_info']['has_next_page']:
                data = self.get_hashtag_json(hashtag,
                                             max_id=data['entry_data']['TagPage'][0]['tag']['media']['page_info'][
                                                 'end_cursor'])
            else:
                break

    def check_id(self, profile: str, json_data: Dict[str, Any]) -> str:
        """
        Consult locally stored ID of profile with given name, check whether ID matches and whether name
        has changed and return current name of the profile, and store ID of profile.
        """
        profile_exists = len(json_data["entry_data"]) > 0 and "ProfilePage" in json_data["entry_data"]
        is_logged_in = json_data["config"]["viewer"] is not None
        if self.profile_subdirs:
            id_filename = profile + "/id"
        else:
            id_filename = profile + "__id"
        try:
            with open(id_filename, 'rb') as id_file:
                profile_id = int(id_file.read())
            if (not profile_exists) or \
                    (profile_id != int(json_data['entry_data']['ProfilePage'][0]['user']['id'])):
                if is_logged_in:
                    newname = self.get_username_by_id(profile_id)
                    self._log("Profile {0} has changed its name to {1}.".format(profile, newname))
                    os.rename(profile, newname)
                    return newname
                if profile_exists:
                    raise ProfileNotExistsException("Profile {0} does not match the stored "
                                                    "unique ID {1}.".format(profile, profile_id))
                raise ProfileNotExistsException("Profile {0} does not exist. Please login to "
                                                "update profile name. Unique ID: {1}."
                                                .format(profile, profile_id))
            return profile
        except FileNotFoundError:
            pass
        if profile_exists:
            if self.profile_subdirs:
                os.makedirs(profile.lower(), exist_ok=True)
            with open(id_filename, 'w') as text_file:
                profile_id = json_data['entry_data']['ProfilePage'][0]['user']['id']
                text_file.write(profile_id + "\n")
                self._log("Stored ID {0} for profile {1}.".format(profile_id, profile))
            return profile
        raise ProfileNotExistsException("Profile {0} does not exist.".format(profile))

    def download(self, name: str,
                 profile_pic_only: bool = False, download_videos: bool = True, geotags: bool = False,
                 fast_update: bool = False) -> None:
        """Download one profile"""
        # pylint:disable=too-many-branches,too-many-locals
        # Get profile main page json
        data = self.get_json(name)
        # check if profile does exist or name has changed since last download
        # and update name and json data if necessary
        name_updated = self.check_id(name, data)
        if name_updated != name:
            name = name_updated
            data = self.get_json(name)
        # Download profile picture
        self.download_profilepic(name, data["entry_data"]["ProfilePage"][0]["user"]["profile_pic_url"])
        if self.sleep:
            time.sleep(1.75 * random.random() + 0.25)
        if profile_pic_only:
            return
        # Catch some errors
        if data["entry_data"]["ProfilePage"][0]["user"]["is_private"]:
            if data["config"]["viewer"] is None:
                raise LoginRequiredException("profile %s requires login" % name)
            if not data["entry_data"]["ProfilePage"][0]["user"]["followed_by_viewer"]:
                raise PrivateProfileNotFollowedException("Profile %s: private but not followed." % name)
        else:
            if data["config"]["viewer"] is not None:
                self._log("profile %s could also be downloaded anonymously." % name)
        if ("nodes" not in data["entry_data"]["ProfilePage"][0]["user"]["media"] or
                not data["entry_data"]["ProfilePage"][0]["user"]["media"]["nodes"]) \
                and not profile_pic_only:
            raise ProfileHasNoPicsException("Profile %s: no pics found." % name)

        # Iterate over pictures and download them
        def get_last_id(data):
            if data["entry_data"] and data["entry_data"]["ProfilePage"][0]["user"]["media"]["nodes"]:
                return data["entry_data"]["ProfilePage"][0]["user"]["media"]["nodes"][-1]["id"]

        totalcount = data["entry_data"]["ProfilePage"][0]["user"]["media"]["count"]
        count = 1
        while get_last_id(data) is not None:
            for node in data["entry_data"]["ProfilePage"][0]["user"]["media"]["nodes"]:
                self._log("[%3i/%3i] " % (count, totalcount), end="", flush=True)
                count += 1
                downloaded = self.download_node(node, name,
                                                download_videos=download_videos, geotags=geotags)
                if fast_update and not downloaded:
                    return
            data = self.get_json(name, max_id=get_last_id(data))

    def interactive_login(self, username: str, password: Optional[str] = None) -> None:
        """Logs in and returns session, asking user for password if needed"""
        if password is not None:
            self.login(username, password)
        if self.quiet:
            raise LoginRequiredException("Quiet mode requires given password or valid session file.")
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
                          fast_update: bool = False, hashtag_lookup_username: bool = False) -> None:
        """Download set of profiles and handle sessions"""
        # pylint:disable=too-many-branches,too-many-locals
        # Login, if desired
        if username is not None:
            self.load_session_from_file(username, sessionfile)
            if username != self.test_login(self.session):
                self.interactive_login(username, password)
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
                                          lookup_username=hashtag_lookup_username)
                elif pentry[0] == '@' and username is not None:
                    self._log("Retrieving followees of %s..." % pentry[1:])
                    followees = self.get_followees(pentry[1:])
                    targets.update([followee['username'] for followee in followees])
                elif pentry == ":feed-all" and username is not None:
                    self._log("Retrieving pictures from your feed...")
                    self.download_feed_pics(fast_update=fast_update, max_count=max_count,
                                            download_videos=download_videos, geotags=geotags)
                elif pentry == ":feed-liked" and username is not None:
                    self._log("Retrieving pictures you liked from your feed...")
                    self.download_feed_pics(fast_update=fast_update, max_count=max_count,
                                            filter_func=lambda node:
                                            not node["likes"]["viewer_has_liked"]
                                            if "likes" in node
                                            else not node["viewer_has_liked"],
                                            download_videos=download_videos, geotags=geotags)
                else:
                    targets.add(pentry)
            if len(targets) > 1:
                self._log("Downloading %i profiles..." % len(targets))
            # Iterate through targets list and download them
            for target in targets:
                try:
                    try:
                        self.download(target, profile_pic_only, download_videos,
                                      geotags, fast_update)
                    except ProfileNotExistsException as err:
                        if username is not None:
                            self._log(
                                "\"Profile not exists\" - Trying again anonymously, helps in case you are just blocked")
                            anonymous_loader = Instaloader(self.sleep, self.quiet, self.shorter_output)
                            anonymous_loader.download(target, profile_pic_only, download_videos,
                                                      geotags, fast_update)
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
    parser = ArgumentParser(description=__doc__,
                            epilog="Report issues at https://github.com/Thammus/instaloader/issues.")
    parser.add_argument('profile', nargs='*', metavar='profile|#hashtag',
                        help='Name of profile or #hashtag to download. '
                             'Alternatively, if --login is given: @<profile> to download all followees of '
                             '<profile>; or the special targets :feed-all or :feed-liked to '
                             'download pictures from your feed (using '
                             '--fast-update is recommended).')
    parser.add_argument('--version', action='version',
                        version=__version__)
    parser.add_argument('-l', '--login', metavar='YOUR-USERNAME',
                        help='Login name for your Instagram account. Not needed to download public '
                             'profiles, but if you want to download private profiles or all followees of '
                             'some profile, you have to specify a username used to login.')
    parser.add_argument('-p', '--password', metavar='YOUR-PASSWORD',
                        help='Password for your Instagram account. If --login is given and there is '
                             'not yet a valid session file, you\'ll be prompted for your password if '
                             '--password is not given. Specifying this option without --login has no '
                             'effect.')
    parser.add_argument('-f', '--sessionfile',
                        help='File to store session key, defaults to ' + get_default_session_filename("<login_name>"))
    parser.add_argument('-P', '--profile-pic-only', action='store_true',
                        help='Only download profile picture')
    parser.add_argument('-V', '--skip-videos', action='store_true',
                        help='Do not download videos')
    parser.add_argument('-G', '--geotags', action='store_true',
                        help='Store geotags when available. This requires an additional request to the Instagram '
                             'server for each picture, which is why it is disabled by default.')
    parser.add_argument('-F', '--fast-update', action='store_true',
                        help='Abort at encounter of first already-downloaded picture')
    parser.add_argument('-c', '--count',
                        help='Do not attempt to download more than COUNT posts. '
                             'Applies only to #hashtag, :feed-all and :feed-liked.')
    parser.add_argument('--no-profile-subdir', action='store_true',
                        help='Instead of creating a subdirectory for each profile and storing pictures there, store '
                             'pictures in files named PROFILE__DATE_TIME.jpg.')
    parser.add_argument('--hashtag-username', action='store_true',
                        help='Lookup username of pictures when downloading by #hashtag and encode it in the downlaoded '
                             'file\'s path or filename (if --no-profile-subdir). Without this option, the #hashtag is '
                             'used instead. This requires an additional request to the Instagram server for each '
                             'picture, which is why it is disabled by default.')
    parser.add_argument('-S', '--no-sleep', action='store_true',
                        help='Do not sleep between actual downloads of pictures')
    parser.add_argument('-O', '--shorter-output', action='store_true',
                        help='Do not display captions while downloading')
    parser.add_argument('-q', '--quiet', action='store_true',
                        help='Disable user interaction, i.e. do not print messages (except errors) and fail '
                             'if login credentials are needed but not given.')
    args = parser.parse_args()
    try:
        loader = Instaloader(not args.no_sleep, args.quiet, args.shorter_output, not args.no_profile_subdir)
        loader.download_profiles(args.profile, args.login, args.password, args.sessionfile,
                                 int(args.count) if args.count is not None else None,
                                 args.profile_pic_only, not args.skip_videos, args.geotags, args.fast_update,
                                 args.hashtag_username)
    except InstaloaderException as err:
        raise SystemExit("Fatal error: %s" % err)


if __name__ == "__main__":
    main()
