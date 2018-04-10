import getpass
import json
import os
import platform
import re
import shutil
import string
import sys
import tempfile
from contextlib import contextmanager, suppress
from datetime import datetime
from enum import Enum
from functools import wraps
from io import BytesIO
from typing import Any, Callable, Dict, Iterator, List, Optional

from .exceptions import *
from .instaloadercontext import InstaloaderContext
from .structures import Post, Profile, Story, StoryItem


def get_default_session_filename(username: str) -> str:
    """Returns default session filename for given username."""
    dirname = tempfile.gettempdir() + "/" + ".instaloader-" + getpass.getuser()
    filename = dirname + "/" + "session-" + username
    return filename.lower()


def format_string_contains_key(format_string: '_PathPattern', key: str) -> bool:
    # pylint:disable=unused-variable
    for literal_text, field_name, format_spec, conversion in string.Formatter().parse(format_string):
        if field_name and (field_name == key or field_name.startswith(key + '.')):
            return True
    return False


class Tristate(Enum):
    """Tri-state to encode whether we should save certain information, i.e. videos, captions, comments or geotags.

    :attr:`never`
        Do not save, even if the information is available without any additional request,

    :attr:`no_extra_query`
        Save if and only if available without doing additional queries,

    :attr:`always`
        Save (and query, if neccessary).
    """
    never = 0
    no_extra_query = 1
    always = 2


def _requires_login(func: Callable) -> Callable:
    """Decorator to raise an exception if herewith-decorated function is called without being logged in"""
    @wraps(func)
    def call(instaloader, *args, **kwargs):
        if not instaloader.context.is_logged_in:
            raise LoginRequiredException("--login=USERNAME required.")
        return func(instaloader, *args, **kwargs)
    # pylint:disable=no-member
    call.__doc__ += ":raises LoginRequiredException: If called without being logged in.\n"
    return call


class _PathPattern(str):
    """Class overriding :meth:`str.format` for character substitution in paths for Windows, see issue #84."""

    def format(self, *args: Any, **kwargs: Any) -> str:
        ret = super().format(*args, **kwargs)
        return ret.replace(':', '\ua789') if platform.system() == 'Windows' else ret


class Instaloader:

    def __init__(self,
                 sleep: bool = True, quiet: bool = False,
                 user_agent: Optional[str] = None,
                 dirname_pattern: Optional[str] = None,
                 filename_pattern: Optional[str] = None,
                 download_videos: Tristate = Tristate.always,
                 download_video_thumbnails: Tristate = Tristate.always,
                 download_geotags: Tristate = Tristate.no_extra_query,
                 save_captions: Tristate = Tristate.no_extra_query,
                 download_comments: Tristate = Tristate.no_extra_query,
                 save_metadata: Tristate = Tristate.never,
                 max_connection_attempts: int = 3):

        self.context = InstaloaderContext(sleep, quiet, user_agent, max_connection_attempts)

        # configuration parameters
        self.dirname_pattern = _PathPattern(dirname_pattern if dirname_pattern is not None else '{target}')
        if filename_pattern is not None:
            filename_pattern = re.sub(r"({(?:post\.)?date)([:}])", r"\1_utc\2", filename_pattern)
            self.filename_pattern_old = filename_pattern.replace('{date_utc}', '{date_utc:%Y-%m-%d_%H-%M-%S}')
            self.filename_pattern_old = _PathPattern(re.sub(r"(?i)({(?:post\.)?date_utc:[^}]*?)_UTC",
                                                            r"\1", self.filename_pattern_old))
            filename_pattern = re.sub(r"(?i)({(date_utc|post\.date_utc):(?![^}]*UTC[^}]*).*?)}",
                                      r"\1_UTC}", filename_pattern)
            self.filename_pattern = _PathPattern(filename_pattern.replace('{date_utc}',
                                                                          '{date_utc:%Y-%m-%d_%H-%M-%S_UTC}'))
        else:
            self.filename_pattern = _PathPattern('{date_utc:%Y-%m-%d_%H-%M-%S_UTC}')
            self.filename_pattern_old = _PathPattern('{date_utc:%Y-%m-%d_%H-%M-%S}')
        self.download_videos = download_videos
        self.download_video_thumbnails = download_video_thumbnails
        self.download_geotags = download_geotags
        self.save_captions = save_captions
        self.download_comments = download_comments
        self.save_metadata = save_metadata

    @contextmanager
    def anonymous_copy(self):
        """Yield an anonymous, otherwise equally-configured copy of an Instaloader instance; Then copy its error log."""
        new_loader = Instaloader(self.context.sleep, self.context.quiet, self.context.user_agent,
                                 self.dirname_pattern, self.filename_pattern,
                                 self.download_videos,
                                 self.download_video_thumbnails,
                                 self.download_geotags,
                                 self.save_captions, self.download_comments,
                                 self.save_metadata, self.context.max_connection_attempts)
        new_loader.context.previous_queries = self.context.previous_queries
        yield new_loader
        self.context.error_log.extend(new_loader.context.error_log)
        new_loader.context.error_log = []  # avoid double-printing of errors
        self.context.previous_queries = new_loader.context.previous_queries
        new_loader.close()

    def close(self):
        self.context.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @_requires_login
    def get_followers(self, profile: Profile) -> Iterator[Dict[str, Any]]:
        """
        Retrieve list of followers of given profile.
        To use this, one needs to be logged in and private profiles has to be followed,
        otherwise this returns an empty list.

        :param profile: Name of profile to lookup followers.
        """
        yield from self.context.graphql_node_list("37479f2b8209594dde7facb0d904896a",
                                                  {'id': str(profile.userid)},
                                                  'https://www.instagram.com/' + profile.username + '/',
                                                  lambda d: d['data']['user']['edge_followed_by'])

    @_requires_login
    def get_followees(self, profile: Profile) -> Iterator[Dict[str, Any]]:
        """
        Retrieve list of followees (followings) of given profile.
        To use this, one needs to be logged in and private profiles has to be followed,
        otherwise this returns an empty list.

        :param profile: Name of profile to lookup followers.
        """
        yield from self.context.graphql_node_list("58712303d941c6855d4e888c5f0cd22f",
                                                  {'id': str(profile.userid)},
                                                  'https://www.instagram.com/' + profile.username + '/',
                                                  lambda d: d['data']['user']['edge_follow'])

    def download_pic(self, filename: str, url: str, mtime: datetime,
                     filename_alt: Optional[str] = None, filename_suffix: Optional[str] = None) -> bool:
        """Downloads and saves picture with given url under given directory with given timestamp.
        Returns true, if file was actually downloaded, i.e. updated."""
        urlmatch = re.search('\\.[a-z0-9]*\\?', url)
        file_extension = url[-3:] if urlmatch is None else urlmatch.group(0)[1:-1]
        if filename_suffix is not None:
            filename += '_' + filename_suffix
            if filename_alt is not None:
                filename_alt += '_' + filename_suffix
        filename += '.' + file_extension
        if os.path.isfile(filename):
            self.context.log(filename + ' exists', end=' ', flush=True)
            return False
        if filename_alt is not None:
            filename_alt += '.' + file_extension
            if os.path.isfile(filename_alt):
                self.context.log(filename_alt + 'exists', end=' ', flush=True)
                return False
        self.context.get_and_write_raw(url, filename)
        os.utime(filename, (datetime.now().timestamp(), mtime.timestamp()))
        return True

    def save_metadata_json(self, filename: str, post: Post) -> None:
        """Saves metadata JSON file of a :class:`Post`."""
        filename += '.json'
        with open(filename, 'w') as fp:
            json.dump(post, fp=fp, indent=4, default=Post.json_encoder)
        self.context.log('json', end=' ', flush=True)

    def update_comments(self, filename: str, post: Post, filename_alt: Optional[str] = None) -> None:
        try:
            filename_current = filename + '_comments.json'
            comments = json.load(open(filename_current))
        except FileNotFoundError:
            try:
                filename_current = filename_alt + '_comments.json'
                comments = json.load(open(filename_current))
            except (FileNotFoundError, TypeError):
                filename_current = filename + '_comments.json'
                comments = list()
        comments.extend(post.get_comments())
        if comments:
            with open(filename_current, 'w') as file:
                comments_list = sorted(sorted(list(comments), key=lambda t: t['id']),
                                       key=lambda t: t['created_at'], reverse=True)
                unique_comments_list = [comments_list[0]]
                #for comment in comments_list:
                #    if unique_comments_list[-1]['id'] != comment['id']:
                #        unique_comments_list.append(comment)
                #file.write(json.dumps(unique_comments_list, indent=4))
                for x, y in zip(comments_list[:-1], comments_list[1:]):
                    if x['id'] != y['id']:
                        unique_comments_list.append(y)
                file.write(json.dumps(unique_comments_list, indent=4))
            os.rename(filename_current, filename + '_comments.json')
            self.context.log('comments', end=' ', flush=True)

    def save_caption(self, filename: str, mtime: datetime, caption: str, filename_alt: Optional[str] = None) -> None:
        """Updates picture caption"""
        filename += '.txt'
        if filename_alt is not None:
            filename_alt += '.txt'
        pcaption = caption.replace('\n', ' ').strip()
        caption = caption.encode("UTF-8")
        pcaption = '[' + ((pcaption[:29] + u"\u2026") if len(pcaption) > 31 else pcaption) + ']'
        with suppress(FileNotFoundError):
            try:
                with open(filename, 'rb') as file:
                    file_caption = file.read()
            except FileNotFoundError:
                if filename_alt is not None:
                    with open(filename_alt, 'rb') as file:
                        file_caption = file.read()
            if file_caption.replace(b'\r\n', b'\n') == caption.replace(b'\r\n', b'\n'):
                try:
                    self.context.log(pcaption + ' unchanged', end=' ', flush=True)
                except UnicodeEncodeError:
                    self.context.log('txt unchanged', end=' ', flush=True)
                return None
            else:
                def get_filename(file, index):
                    return file if index == 0 else (file[:-4] + '_old_' +
                                                    (str(0) if index < 10 else str()) + str(index) + file[-4:])

                i = 0
                file_exists_list = []
                while True:
                    file_exists_list.append(1 if os.path.isfile(get_filename(filename, i)) else 0)
                    if not file_exists_list[i] and filename_alt is not None:
                        file_exists_list[i] = 2 if os.path.isfile(get_filename(filename_alt, i)) else 0
                    if not file_exists_list[i]:
                        break
                    i = i + 1
                for index in range(i, 0, -1):
                    os.rename(get_filename(filename if file_exists_list[index - 1] % 2 else filename_alt, index - 1),
                              get_filename(filename, index))
                try:
                    self.context.log(pcaption + ' updated', end=' ', flush=True)
                except UnicodeEncodeError:
                    self.context.log('txt updated', end=' ', flush=True)
        try:
            self.context.log(pcaption, end=' ', flush=True)
        except UnicodeEncodeError:
            self.context.log('txt', end=' ', flush=True)
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
        self.context.log('geo', end=' ', flush=True)

    def download_profilepic(self, profile: Profile) -> None:
        """Downloads and saves profile pic."""

        def _epoch_to_string(epoch: datetime) -> str:
            return epoch.strftime('%Y-%m-%d_%H-%M-%S')

        profile_pic_url = profile.get_profile_pic_url()
        with self.context.get_anonymous_session() as anonymous_session:
            date_object = datetime.strptime(anonymous_session.head(profile_pic_url).headers["Last-Modified"],
                                            '%a, %d %b %Y %H:%M:%S GMT')
        if ((format_string_contains_key(self.dirname_pattern, 'profile') or
             format_string_contains_key(self.dirname_pattern, 'target'))):
            filename = '{0}/{1}_UTC_profile_pic.{2}'.format(self.dirname_pattern.format(profile=profile.username.lower(),
                                                                                        target=profile.username.lower()),
                                                            _epoch_to_string(date_object), profile_pic_url[-3:])
        else:
            filename = '{0}/{1}_{2}_UTC_profile_pic.{3}'.format(self.dirname_pattern.format(), profile.username.lower(),
                                                                _epoch_to_string(date_object), profile_pic_url[-3:])
        if os.path.isfile(filename):
            self.context.log(filename + ' already exists')
            return None
        self.context.get_and_write_raw(profile_pic_url, filename)
        os.utime(filename, (datetime.now().timestamp(), date_object.timestamp()))
        self.context.log('')  # log output of _get_and_write_raw() does not produce \n

    @_requires_login
    def save_session_to_file(self, filename: Optional[str] = None) -> None:
        """Saves internally stored :class:`requests.Session` object."""
        if filename is None:
            filename = get_default_session_filename(self.context.username)
        dirname = os.path.dirname(filename)
        if dirname != '' and not os.path.exists(dirname):
            os.makedirs(dirname)
            os.chmod(dirname, 0o700)
        with open(filename, 'wb') as sessionfile:
            os.chmod(filename, 0o600)
            self.context.save_session_to_file(sessionfile)
            self.context.log("Saved session to %s." % filename)

    def load_session_from_file(self, username: str, filename: Optional[str] = None) -> None:
        """Internally stores :class:`requests.Session` object loaded from file.

        If filename is None, the file with the default session path is loaded.

        :raises FileNotFoundError: If the file does not exist.
        """
        if filename is None:
            filename = get_default_session_filename(username)
        with open(filename, 'rb') as sessionfile:
            self.context.load_session_from_file(username, sessionfile)
            self.context.log("Loaded session from %s." % filename)

    def test_login(self) -> Optional[str]:
        """Returns the Instagram username to which given :class:`requests.Session` object belongs, or None."""
        return self.context.test_login()

    def login(self, user: str, passwd: str) -> None:
        """Log in to instagram with given username and password and internally store session object"""
        self.context.login(user, passwd)

    def download_post(self, post: Post, target: str) -> bool:
        """
        Download everything associated with one instagram post node, i.e. picture, caption and video.

        :param post: Post to download.
        :param target: Target name, i.e. profile name, #hashtag, :feed; for filename.
        :return: True if something was downloaded, False otherwise, i.e. file was already there
        """

        # Format dirname and filename. post.owner_username might do an additional request, so only access it, if
        # {profile} is part of the dirname pattern or filename pattern.
        needs_profilename = (format_string_contains_key(self.dirname_pattern, 'profile') or
                             format_string_contains_key(self.filename_pattern, 'profile'))
        profilename = post.owner_username if needs_profilename else None
        dirname = self.dirname_pattern.format(profile=profilename, target=target.lower())
        filename = dirname + '/' + self.filename_pattern.format(profile=profilename, target=target.lower(),
                                                                date_utc=post.date_utc,
                                                                shortcode=post.shortcode,
                                                                post=post)
        filename_old = dirname + '/' + self.filename_pattern_old.replace("{post.date_utc", "{date_utc") \
                                                                .format(profile=profilename, target=target.lower(),
                                                                        date_utc=post.date_local,
                                                                        shortcode=post.shortcode,
                                                                        post=post)
        os.makedirs(os.path.dirname(filename), exist_ok=True)

        # Download the image(s) / video thumbnail and videos within sidecars if desired
        downloaded = False
        if post.typename == 'GraphSidecar':
            edge_number = 1
            for edge in post.get_sidecar_edges():
                # Download picture or video thumbnail
                if not edge['node']['is_video'] or self.download_video_thumbnails is Tristate.always:
                    downloaded |= self.download_pic(filename=filename,
                                                    filename_alt=filename_old,
                                                    url=edge['node']['display_url'],
                                                    mtime=post.date_local,
                                                    filename_suffix=str(edge_number))
                # Additionally download video if available and desired
                if edge['node']['is_video'] and self.download_videos is Tristate.always:
                    downloaded |= self.download_pic(filename=filename,
                                                    filename_alt=filename_old,
                                                    url=edge['node']['video_url'],
                                                    mtime=post.date_local,
                                                    filename_suffix=str(edge_number))
                edge_number += 1
        elif post.typename == 'GraphImage':
            downloaded = self.download_pic(filename=filename, filename_alt=filename_old,
                                           url=post.url, mtime=post.date_local)
        elif post.typename == 'GraphVideo':
            if self.download_video_thumbnails is Tristate.always:
                downloaded = self.download_pic(filename=filename, filename_alt=filename_old,
                                               url=post.url, mtime=post.date_local)
        else:
            self.context.error("Warning: {0} has unknown typename: {1}".format(post, post.typename))

        # Save caption if desired
        if self.save_captions is not Tristate.never:
            if post.caption:
                self.save_caption(filename=filename, filename_alt=filename_old,
                                  mtime=post.date_local, caption=post.caption)
            else:
                self.context.log("<no caption>", end=' ', flush=True)

        # Download video if desired
        if post.is_video and self.download_videos is Tristate.always:
            downloaded |= self.download_pic(filename=filename, filename_alt=filename_old,
                                            url=post.video_url, mtime=post.date_local)

        # Download geotags if desired
        if self.download_geotags is Tristate.always:
            location = post.get_location()
            if location:
                self.save_location(filename, location, post.date_local)

        # Update comments if desired
        if self.download_comments is Tristate.always:
            self.update_comments(filename=filename, filename_alt=filename_old, post=post)

        # Save metadata as JSON if desired.  It might require an extra query, depending on which information has been
        # already obtained.  Regarding Tristate interpretation, we always assume that it requires an extra query.
        if self.save_metadata is Tristate.always:
            self.save_metadata_json(filename, post)

        self.context.log()
        return downloaded

    @_requires_login
    def get_stories(self, userids: Optional[List[int]] = None) -> Iterator[Story]:
        """Get available stories from followees or all stories of users whose ID are given.
        Does not mark stories as seen.
        To use this, one needs to be logged in

        :param userids: List of user IDs to be processed in terms of downloading their stories, or None.
        """

        if userids is None:
            data = self.context.graphql_query("d15efd8c0c5b23f0ef71f18bf363c704",
                                              {"only_stories": True})["data"]["user"]
            if data is None:
                raise BadResponseException('Bad stories reel JSON.')
            userids = list(edge["node"]["id"] for edge in data["feed_reels_tray"]["edge_reels_tray_to_reel"]["edges"])

        stories = self.context.graphql_query("bf41e22b1c4ba4c9f31b844ebb7d9056",
                                             {"reel_ids": userids, "precomposed_overlay": False})["data"]

        yield from (Story(self.context, media) for media in stories['reels_media'])

    @_requires_login
    def download_stories(self,
                         userids: Optional[List[int]] = None,
                         fast_update: bool = False,
                         filename_target: str = ':stories') -> None:
        """
        Download available stories from user followees or all stories of users whose ID are given.
        Does not mark stories as seen.
        To use this, one needs to be logged in

        :param userids: List of user IDs to be processed in terms of downloading their stories
        :param fast_update: If true, abort when first already-downloaded picture is encountered
        :param filename_target: Replacement for {target} in dirname_pattern and filename_pattern
        """

        if not userids:
            self.context.log("Retrieving all visible stories...")

        if format_string_contains_key(self.filename_pattern, 'post'):
            raise InvalidArgumentException("The \"post\" keyword is not supported in the filename pattern when "
                                           "downloading stories.")

        for user_story in self.get_stories(userids):
            name = user_story.owner_username
            self.context.log("Retrieving stories from profile {}.".format(name))
            totalcount = user_story.itemcount
            count = 1
            for item in user_story.get_items():
                self.context.log("[%3i/%3i] " % (count, totalcount), end="", flush=True)
                count += 1
                with self.context.error_catcher('Download story from user {}'.format(name)):
                    downloaded = self.download_story(item, filename_target)
                    if fast_update and not downloaded:
                        break

    def download_story(self, item: StoryItem, target: str) -> bool:
        """Download one user story.

        :param item: Story item, as in story['items'] for story in :meth:`get_stories`
        :param target: Replacement for {target} in dirname_pattern and filename_pattern
        :return: True if something was downloaded, False otherwise, i.e. file was already there
        """

        owner_name = item.owner_username
        shortcode = item.shortcode
        date_local = item.date_local
        date_utc = item.date_utc
        dirname = self.dirname_pattern.format(profile=owner_name, target=target)
        filename = dirname + '/' + self.filename_pattern.format(profile=owner_name, target=target,
                                                                date_utc=date_utc,
                                                                shortcode=shortcode)
        filename_old = dirname + '/' + self.filename_pattern_old.format(profile=owner_name, target=target,
                                                                        date_utc=date_local,
                                                                        shortcode=shortcode)
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        downloaded = False
        if not item.is_video or self.download_video_thumbnails is Tristate.always:
            url = item.url
            downloaded = self.download_pic(filename=filename,
                                           filename_alt=filename_old,
                                           url=url,
                                           mtime=date_local)
        if item.is_video and self.download_videos is Tristate.always:
            downloaded |= self.download_pic(filename=filename,
                                            filename_alt=filename_old,
                                            url=item.video_url,
                                            mtime=date_local)
        self.context.log()
        return downloaded

    @_requires_login
    def get_feed_posts(self) -> Iterator[Post]:
        """Get Posts of the user's feed."""

        data = self.context.graphql_query("d6f4427fbe92d846298cf93df0b937d3", {})["data"]

        while True:
            feed = data["user"]["edge_web_feed_timeline"]
            yield from (Post(self.context, edge["node"]) for edge in feed["edges"]
                        if not edge["node"]["__typename"] == "GraphSuggestedUserFeedUnit")
            if not feed["page_info"]["has_next_page"]:
                break
            data = self.context.graphql_query("d6f4427fbe92d846298cf93df0b937d3",
                                              {'fetch_media_item_count': 12,
                                               'fetch_media_item_cursor': feed["page_info"]["end_cursor"],
                                               'fetch_comment_count': 4,
                                               'fetch_like': 10,
                                               'has_stories': False})["data"]

    @_requires_login
    def download_feed_posts(self, max_count: int = None, fast_update: bool = False,
                            filter_func: Optional[Callable[[Post], bool]] = None) -> None:
        """
        Download pictures from the user's feed.

        Example to download up to the 20 pics the user last liked::

            loader = Instaloader()
            loader.load_session_from_file('USER')
            loader.download_feed_posts(max_count=20, fast_update=True,
                                       filter_func=lambda post: post.viewer_has_liked)

        :param max_count: Maximum count of pictures to download
        :param fast_update: If true, abort when first already-downloaded picture is encountered
        :param filter_func: function(post), which returns True if given picture should be downloaded
        """
        self.context.log("Retrieving pictures from your feed...")
        count = 1
        for post in self.get_feed_posts():
            if max_count is not None and count > max_count:
                break
            name = post.owner_username
            if filter_func is not None and not filter_func(post):
                self.context.log("<pic by %s skipped>" % name, flush=True)
                continue
            self.context.log("[%3i] %s " % (count, name), end="", flush=True)
            count += 1
            with self.context.error_catcher('Download feed'):
                downloaded = self.download_post(post, target=':feed')
                if fast_update and not downloaded:
                    break

    @_requires_login
    def download_saved_posts(self, max_count: int = None, fast_update: bool = False,
                             filter_func: Optional[Callable[[Post], bool]] = None) -> None:
        """Download user's saved pictures.

        :param max_count: Maximum count of pictures to download
        :param fast_update: If true, abort when first already-downloaded picture is encountered
        :param filter_func: function(post), which returns True if given picture should be downloaded
        """
        self.context.log("Retrieving saved posts...")
        count = 1
        for post in Profile.from_username(self.context, self.context.username).get_saved_posts():
            if max_count is not None and count > max_count:
                break
            name = post.owner_username
            if filter_func is not None and not filter_func(post):
                self.context.log("<pic by {} skipped".format(name), flush=True)
                continue
            self.context.log("[{:>3}] {} ".format(count, name), end=str(), flush=True)
            count += 1
            with self.context.error_catcher('Download saved posts'):
                downloaded = self.download_post(post, target=':saved')
                if fast_update and not downloaded:
                    break

    @_requires_login
    def get_explore_posts(self) -> Iterator[Post]:
        """Get Posts which are worthy of exploring suggested by Instagram."""
        yield from (Post(self.context, node)
                    for node in self.context.graphql_node_list("df0dcc250c2b18d9fd27c5581ef33c7c",
                                                               {}, 'https://www.instagram.com/explore/',
                                                               lambda d: d['data']['user']['edge_web_discover_media']))

    def get_hashtag_posts(self, hashtag: str) -> Iterator[Post]:
        """Get Posts associated with a #hashtag."""
        yield from (Post(self.context, node)
                    for node in self.context.graphql_node_list("298b92c8d7cad703f7565aa892ede943",
                                                               {'tag_name': hashtag},
                                                               'https://www.instagram.com/explore/tags/{0}/'
                                                               .format(hashtag),
                                                               lambda d: d['data']['hashtag']['edge_hashtag_to_media']))

    def download_hashtag(self, hashtag: str,
                         max_count: Optional[int] = None,
                         filter_func: Optional[Callable[[Post], bool]] = None,
                         fast_update: bool = False) -> None:
        """Download pictures of one hashtag.

        To download the last 30 pictures with hashtag #cat, do::

            loader = Instaloader()
            loader.download_hashtag('cat', max_count=30)

        :param hashtag: Hashtag to download, without leading '#'
        :param max_count: Maximum count of pictures to download
        :param filter_func: function(post), which returns True if given picture should be downloaded
        :param fast_update: If true, abort when first already-downloaded picture is encountered
        """
        hashtag = hashtag.lower()
        self.context.log("Retrieving pictures with hashtag {}...".format(hashtag))
        count = 1
        for post in self.get_hashtag_posts(hashtag):
            if max_count is not None and count > max_count:
                break
            self.context.log('[{0:3d}] #{1} '.format(count, hashtag), end='', flush=True)
            if filter_func is not None and not filter_func(post):
                self.context.log('<skipped>')
                continue
            count += 1
            with self.context.error_catcher('Download hashtag #{}'.format(hashtag)):
                downloaded = self.download_post(post, target='#' + hashtag)
                if fast_update and not downloaded:
                    break

    def check_profile_id(self, profile_name: str) -> Profile:
        """
        Consult locally stored ID of profile with given name, check whether ID matches and whether name
        has changed and return current name of the profile, and store ID of profile.

        :param profile_name: Profile name
        :return: Instance of current profile
        """
        profile = None
        with suppress(ProfileNotExistsException):
            profile = Profile.from_username(self.context, profile_name)
        profile_exists = profile is not None
        if ((format_string_contains_key(self.dirname_pattern, 'profile') or
             format_string_contains_key(self.dirname_pattern, 'target'))):
            id_filename = '{0}/id'.format(self.dirname_pattern.format(profile=profile_name.lower(),
                                                                      target=profile_name.lower()))
        else:
            id_filename = '{0}/{1}_id'.format(self.dirname_pattern.format(), profile_name.lower())
        try:
            with open(id_filename, 'rb') as id_file:
                profile_id = int(id_file.read())
            if (not profile_exists) or \
                    (profile_id != profile.userid):
                if profile_exists:
                    self.context.log("Profile {0} does not match the stored unique ID {1}.".format(profile_name,
                                                                                                   profile_id))
                else:
                    self.context.log("Trying to find profile {0} using its unique ID {1}.".format(profile_name,
                                                                                                  profile_id))
                profile_from_id = Profile.from_id(self.context, profile_id)
                newname = profile_from_id.username
                self.context.log("Profile {0} has changed its name to {1}.".format(profile_name, newname))
                if ((format_string_contains_key(self.dirname_pattern, 'profile') or
                     format_string_contains_key(self.dirname_pattern, 'target'))):
                    os.rename(self.dirname_pattern.format(profile=profile_name.lower(),
                                                          target=profile_name.lower()),
                              self.dirname_pattern.format(profile=newname.lower(),
                                                          target=newname.lower()))
                else:
                    os.rename('{0}/{1}_id'.format(self.dirname_pattern.format(), profile_name.lower()),
                              '{0}/{1}_id'.format(self.dirname_pattern.format(), newname.lower()))
                return profile_from_id
            return profile
        except FileNotFoundError:
            pass
        if profile_exists:
            os.makedirs(self.dirname_pattern.format(profile=profile_name.lower(),
                                                    target=profile_name.lower()), exist_ok=True)
            with open(id_filename, 'w') as text_file:
                text_file.write(str(profile.userid) + "\n")
                self.context.log("Stored ID {0} for profile {1}.".format(profile.userid, profile_name))
            return profile
        raise ProfileNotExistsException("Profile {0} does not exist.".format(profile_name))

    def download_profile(self, profile_name: str,
                         profile_pic: bool = True, profile_pic_only: bool = False,
                         fast_update: bool = False,
                         download_stories: bool = False, download_stories_only: bool = False,
                         filter_func: Optional[Callable[[Post], bool]] = None) -> None:
        """Download one profile"""

        # Get profile main page json
        # check if profile does exist or name has changed since last download
        # and update name and json data if necessary
        profile = self.check_profile_id(profile_name.lower())

        profile_name = profile.username

        if self.context.is_logged_in and profile.has_blocked_viewer and not profile.is_private:
            # raising ProfileNotExistsException invokes "trying again anonymously" logic
            raise ProfileNotExistsException("Profile {} has blocked you".format(profile_name))

        # Download profile picture
        if profile_pic or profile_pic_only:
            with self.context.error_catcher('Download profile picture of {}'.format(profile_name)):
                self.download_profilepic(profile)
        if profile_pic_only:
            return

        # Catch some errors
        if profile.is_private:
            if not self.context.is_logged_in:
                raise LoginRequiredException("profile %s requires login" % profile_name)
            if not profile.followed_by_viewer and \
                    self.context.username != profile.username:
                raise PrivateProfileNotFollowedException("Profile %s: private but not followed." % profile_name)
        else:
            if self.context.is_logged_in and not (download_stories or download_stories_only):
                self.context.log("profile %s could also be downloaded anonymously." % profile_name)

        # Download stories, if requested
        if download_stories or download_stories_only:
            with self.context.error_catcher("Download stories of {}".format(profile_name)):
                self.download_stories(userids=[profile.userid], filename_target=profile_name, fast_update=fast_update)
        if download_stories_only:
            return

        # Iterate over pictures and download them
        self.context.log("Retrieving posts from profile {}.".format(profile_name))
        totalcount = profile.mediacount
        count = 1
        for post in profile.get_posts():
            self.context.log("[%3i/%3i] " % (count, totalcount), end="", flush=True)
            count += 1
            if filter_func is not None and not filter_func(post):
                self.context.log('<skipped>')
                continue
            with self.context.error_catcher('Download profile {}'.format(profile_name)):
                downloaded = self.download_post(post, target=profile_name)
                if fast_update and not downloaded:
                    break

    def interactive_login(self, username: str) -> None:
        """Logs in and internally stores session, asking user for password interactively.

        :raises LoginRequiredException: when in quiet mode."""
        if self.context.quiet:
            raise LoginRequiredException("Quiet mode requires given password or valid session file.")
        password = None
        while password is None:
            password = getpass.getpass(prompt="Enter Instagram password for %s: " % username)
            try:
                self.login(username, password)
            except BadCredentialsException as err:
                print(err, file=sys.stderr)
                password = None
