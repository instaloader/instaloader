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
from datetime import datetime, timezone
from functools import wraps
from io import BytesIO
from typing import Any, Callable, Iterator, List, Optional, Set, Union

from .exceptions import *
from .instaloadercontext import InstaloaderContext
from .structures import Highlight, JsonExportable, Post, PostLocation, Profile, Story, StoryItem, save_structure_to_file


def get_default_session_filename(username: str) -> str:
    """Returns default session filename for given username."""
    dirname = tempfile.gettempdir() + "/" + ".instaloader-" + getpass.getuser()
    filename = dirname + "/" + "session-" + username
    return filename.lower()


def format_string_contains_key(format_string: str, key: str) -> bool:
    # pylint:disable=unused-variable
    for literal_text, field_name, format_spec, conversion in string.Formatter().parse(format_string):
        if field_name and (field_name == key or field_name.startswith(key + '.')):
            return True
    return False


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


class _ArbitraryItemFormatter(string.Formatter):
    def __init__(self, item: Any):
        self._item = item

    def get_value(self, key, args, kwargs):
        """Override to substitute {ATTRIBUTE} by attributes of our _item."""
        if hasattr(self._item, key):
            return getattr(self._item, key)
        return super().get_value(key, args, kwargs)

    def format_field(self, value, format_spec):
        """Override :meth:`string.Formatter.format_field` to have our
         default format_spec for :class:`datetime.Datetime` objects, and to
         let None yield an empty string rather than ``None``."""
        if isinstance(value, datetime) and not format_spec:
            return super().format_field(value, '%Y-%m-%d_%H-%M-%S')
        if value is None:
            return ''
        return super().format_field(value, format_spec)


class _PostPathFormatter(_ArbitraryItemFormatter):
    def vformat(self, format_string, args, kwargs):
        """Override :meth:`string.Formatter.vformat` for character substitution in paths for Windows, see issue #84."""
        ret = super().vformat(format_string, args, kwargs)
        if platform.system() == 'Windows':
            ret = ret.replace(':', '\ua789').replace('<', '\ufe64').replace('>', '\ufe65').replace('\"', '\uff02')
            ret = ret.replace('\\', '\uff3c').replace('|', '\uff5c').replace('?', '\ufe16').replace('*', '\uff0a')
        return ret


class Instaloader:
    """Instaloader Class.

    :param quiet: :option:`--quiet`
    :param user_agent: :option:`--user-agent`
    :param dirname_pattern: :option:`--dirname-pattern`, default is ``{target}``
    :param filename_pattern: :option:`--filename-pattern`, default is ``{date_utc}_UTC``
    :param download_pictures: not :option:`--no-pictures`
    :param download_videos: not :option:`--no-videos`
    :param download_video_thumbnails: not :option:`--no-video-thumbnails`
    :param download_geotags: :option:`--geotags`
    :param download_comments: :option:`--comments`
    :param save_metadata: not :option:`--no-metadata-json`
    :param compress_json: not :option:`--no-compress-json`
    :param post_metadata_txt_pattern:
       :option:`--post-metadata-txt`, default is ``{caption}``. Set to empty string to avoid creation of post metadata
       txt file.
    :param storyitem_metadata_txt_pattern: :option:`--storyitem-metadata-txt`, default is empty (=none)
    :param max_connection_attempts: :option:`--max-connection-attempts`

    .. attribute:: context

       The associated :class:`InstaloaderContext` with low-level communication functions and logging.
    """

    def __init__(self,
                 sleep: bool = True, quiet: bool = False,
                 user_agent: Optional[str] = None,
                 dirname_pattern: Optional[str] = None,
                 filename_pattern: Optional[str] = None,
                 download_pictures=True,
                 download_videos: bool = True,
                 download_video_thumbnails: bool = True,
                 download_geotags: bool = True,
                 download_comments: bool = True,
                 save_metadata: bool = True,
                 compress_json: bool = True,
                 post_metadata_txt_pattern: str = None,
                 storyitem_metadata_txt_pattern: str = None,
                 graphql_rate_limit: Optional[int] = None,
                 max_connection_attempts: int = 3):

        self.context = InstaloaderContext(sleep, quiet, user_agent, graphql_rate_limit, max_connection_attempts)

        # configuration parameters
        self.dirname_pattern = dirname_pattern or "{target}"
        self.filename_pattern = filename_pattern or "{date_utc}_UTC"
        self.download_pictures = download_pictures
        self.download_videos = download_videos
        self.download_video_thumbnails = download_video_thumbnails
        self.download_geotags = download_geotags
        self.download_comments = download_comments
        self.save_metadata = save_metadata
        self.compress_json = compress_json
        self.post_metadata_txt_pattern = '{caption}' if post_metadata_txt_pattern is None \
            else post_metadata_txt_pattern
        self.storyitem_metadata_txt_pattern = '' if storyitem_metadata_txt_pattern is None \
            else storyitem_metadata_txt_pattern

    @contextmanager
    def anonymous_copy(self):
        """Yield an anonymous, otherwise equally-configured copy of an Instaloader instance; Then copy its error log."""
        new_loader = Instaloader(self.context.sleep, self.context.quiet, self.context.user_agent, self.dirname_pattern,
                                 self.filename_pattern, download_pictures=self.download_pictures,
                                 download_videos=self.download_videos,
                                 download_video_thumbnails=self.download_video_thumbnails,
                                 download_geotags=self.download_geotags, download_comments=self.download_comments,
                                 save_metadata=self.save_metadata, compress_json=self.compress_json,
                                 post_metadata_txt_pattern=self.post_metadata_txt_pattern,
                                 storyitem_metadata_txt_pattern=self.storyitem_metadata_txt_pattern,
                                 graphql_rate_limit=self.context.graphql_count_per_slidingwindow,
                                 max_connection_attempts=self.context.max_connection_attempts)
        new_loader.context.query_timestamps = self.context.query_timestamps
        yield new_loader
        self.context.error_log.extend(new_loader.context.error_log)
        new_loader.context.error_log = []  # avoid double-printing of errors
        self.context.query_timestamps = new_loader.context.query_timestamps
        new_loader.close()

    def close(self):
        """Close associated session objects and repeat error log."""
        self.context.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def download_pic(self, filename: str, url: str, mtime: datetime, filename_suffix: Optional[str] = None) -> bool:
        """Downloads and saves picture with given url under given directory with given timestamp.
        Returns true, if file was actually downloaded, i.e. updated."""
        urlmatch = re.search('\\.[a-z0-9]*\\?', url)
        file_extension = url[-3:] if urlmatch is None else urlmatch.group(0)[1:-1]
        if filename_suffix is not None:
            filename += '_' + filename_suffix
        filename += '.' + file_extension
        if os.path.isfile(filename):
            self.context.log(filename + ' exists', end=' ', flush=True)
            return False
        self.context.get_and_write_raw(url, filename)
        os.utime(filename, (datetime.now().timestamp(), mtime.timestamp()))
        return True

    def save_metadata_json(self, filename: str, structure: JsonExportable) -> None:
        """Saves metadata JSON file of a structure."""
        if self.compress_json:
            filename += '.json.xz'
        else:
            filename += '.json'
        save_structure_to_file(structure, filename)
        if isinstance(structure, (Post, StoryItem)):
            # log 'json ' message when saving Post or StoryItem
            self.context.log('json', end=' ', flush=True)

    def update_comments(self, filename: str, post: Post) -> None:
        def _postcomment_asdict(comment):
            return {'id': comment.id,
                    'created_at': int(comment.created_at_utc.replace(tzinfo=timezone.utc).timestamp()),
                    'text': comment.text,
                    'owner': comment.owner._asdict()}
        filename += '_comments.json'
        try:
            with open(filename) as fp:
                comments = json.load(fp)
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            comments = list()
        comments.extend(_postcomment_asdict(comment) for comment in post.get_comments())
        if comments:
            comments_list = sorted(sorted(list(comments), key=lambda t: int(t['id'])),
                                   key=lambda t: int(t['created_at']), reverse=True)
            unique_comments_list = [comments_list[0]]
            #for comment in comments_list:
            #    if unique_comments_list[-1]['id'] != comment['id']:
            #        unique_comments_list.append(comment)
            #file.write(json.dumps(unique_comments_list, indent=4))
            for x, y in zip(comments_list[:-1], comments_list[1:]):
                if x['id'] != y['id']:
                    unique_comments_list.append(y)
            with open(filename, 'w') as file:
                file.write(json.dumps(unique_comments_list, indent=4))
            self.context.log('comments', end=' ', flush=True)

    def save_caption(self, filename: str, mtime: datetime, caption: str) -> None:
        """Updates picture caption / Post metadata info"""
        def _elliptify(caption):
            pcaption = caption.replace('\n', ' ').strip()
            return '[' + ((pcaption[:29] + u"\u2026") if len(pcaption) > 31 else pcaption) + ']'
        filename += '.txt'
        caption += '\n'
        pcaption = _elliptify(caption)
        caption = caption.encode("UTF-8")
        with suppress(FileNotFoundError):
            with open(filename, 'rb') as file:
                file_caption = file.read()
            if file_caption.replace(b'\r\n', b'\n') == caption.replace(b'\r\n', b'\n'):
                try:
                    self.context.log(pcaption + ' unchanged', end=' ', flush=True)
                except UnicodeEncodeError:
                    self.context.log('txt unchanged', end=' ', flush=True)
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
                    self.context.log(_elliptify(file_caption.decode("UTF-8")) + ' updated', end=' ', flush=True)
                except UnicodeEncodeError:
                    self.context.log('txt updated', end=' ', flush=True)
        try:
            self.context.log(pcaption, end=' ', flush=True)
        except UnicodeEncodeError:
            self.context.log('txt', end=' ', flush=True)
        with open(filename, 'wb') as text_file:
            shutil.copyfileobj(BytesIO(caption), text_file)
        os.utime(filename, (datetime.now().timestamp(), mtime.timestamp()))

    def save_location(self, filename: str, location: PostLocation, mtime: datetime) -> None:
        """Save post location name and Google Maps link."""
        filename += '_location.txt'
        location_string = (location.name + "\n" +
                           "https://maps.google.com/maps?q={0},{1}&ll={0},{1}\n".format(location.lat,
                                                                                        location.lng))
        with open(filename, 'wb') as text_file:
            shutil.copyfileobj(BytesIO(location_string.encode()), text_file)
        os.utime(filename, (datetime.now().timestamp(), mtime.timestamp()))
        self.context.log('geo', end=' ', flush=True)

    def download_profilepic(self, profile: Profile) -> None:
        """Downloads and saves profile pic."""

        def _epoch_to_string(epoch: datetime) -> str:
            return epoch.strftime('%Y-%m-%d_%H-%M-%S')

        profile_pic_url = profile.profile_pic_url
        with self.context.get_anonymous_session() as anonymous_session:
            date_object = datetime.strptime(anonymous_session.head(profile_pic_url).headers["Last-Modified"],
                                            '%a, %d %b %Y %H:%M:%S GMT')
        profile_pic_extension = 'jpg'
        if ((format_string_contains_key(self.dirname_pattern, 'profile') or
             format_string_contains_key(self.dirname_pattern, 'target'))):
            filename = '{0}/{1}_UTC_profile_pic.{2}'.format(self.dirname_pattern.format(profile=profile.username.lower(),
                                                                                        target=profile.username.lower()),
                                                            _epoch_to_string(date_object), profile_pic_extension)
        else:
            filename = '{0}/{1}_{2}_UTC_profile_pic.{3}'.format(self.dirname_pattern.format(), profile.username.lower(),
                                                                _epoch_to_string(date_object), profile_pic_extension)
        if os.path.isfile(filename):
            self.context.log(filename + ' already exists')
            return None
        self.context.get_and_write_raw(profile_pic_url, filename)
        os.utime(filename, (datetime.now().timestamp(), date_object.timestamp()))
        self.context.log('')  # log output of _get_and_write_raw() does not produce \n

    @_requires_login
    def save_session_to_file(self, filename: Optional[str] = None) -> None:
        """Saves internally stored :class:`requests.Session` object.

        :param filename: Filename, or None to use default filename.
        """
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
        """Log in to instagram with given username and password and internally store session object.

        :raises InvalidArgumentException: If the provided username does not exist.
        :raises BadCredentialsException: If the provided password is wrong.
        :raises ConnectionException: If connection to Instagram failed."""
        self.context.login(user, passwd)

    def format_filename(self, item: Union[Post, StoryItem], target: Optional[str] = None):
        """Format filename of a :class:`Post` or :class:`StoryItem` according to ``filename-pattern`` parameter.

        .. versionadded:: 4.1"""
        return _PostPathFormatter(item).format(self.filename_pattern, target=target)

    def download_post(self, post: Post, target: str) -> bool:
        """
        Download everything associated with one instagram post node, i.e. picture, caption and video.

        :param post: Post to download.
        :param target: Target name, i.e. profile name, #hashtag, :feed; for filename.
        :return: True if something was downloaded, False otherwise, i.e. file was already there
        """

        dirname = _PostPathFormatter(post).format(self.dirname_pattern, target=target)
        filename = dirname + '/' + self.format_filename(post, target=target)
        os.makedirs(os.path.dirname(filename), exist_ok=True)

        # Download the image(s) / video thumbnail and videos within sidecars if desired
        downloaded = False
        if self.download_pictures:
            if post.typename == 'GraphSidecar':
                edge_number = 1
                for sidecar_node in post.get_sidecar_nodes():
                    # Download picture or video thumbnail
                    if not sidecar_node.is_video or self.download_video_thumbnails is True:
                        downloaded |= self.download_pic(filename=filename, url=sidecar_node.display_url,
                                                        mtime=post.date_local, filename_suffix=str(edge_number))
                    # Additionally download video if available and desired
                    if sidecar_node.is_video and self.download_videos is True:
                        downloaded |= self.download_pic(filename=filename, url=sidecar_node.video_url,
                                                        mtime=post.date_local, filename_suffix=str(edge_number))
                    edge_number += 1
            elif post.typename == 'GraphImage':
                downloaded = self.download_pic(filename=filename, url=post.url, mtime=post.date_local)
            elif post.typename == 'GraphVideo':
                if self.download_video_thumbnails is True:
                    downloaded = self.download_pic(filename=filename, url=post.url, mtime=post.date_local)
            else:
                self.context.error("Warning: {0} has unknown typename: {1}".format(post, post.typename))

        # Save caption if desired
        metadata_string = _ArbitraryItemFormatter(post).format(self.post_metadata_txt_pattern).strip()
        if metadata_string:
            self.save_caption(filename=filename, mtime=post.date_local, caption=metadata_string)

        # Download video if desired
        if post.is_video and self.download_videos is True:
            downloaded |= self.download_pic(filename=filename, url=post.video_url, mtime=post.date_local)

        # Download geotags if desired
        if self.download_geotags and post.location:
            self.save_location(filename, post.location, post.date_local)

        # Update comments if desired
        if self.download_comments is True:
            self.update_comments(filename=filename, post=post)

        # Save metadata as JSON if desired.
        if self.save_metadata is not False:
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

        if not userids:
            data = self.context.graphql_query("d15efd8c0c5b23f0ef71f18bf363c704",
                                              {"only_stories": True})["data"]["user"]
            if data is None:
                raise BadResponseException('Bad stories reel JSON.')
            userids = list(edge["node"]["id"] for edge in data["feed_reels_tray"]["edge_reels_tray_to_reel"]["edges"])

        def _userid_chunks():
            userids_per_query = 100
            for i in range(0, len(userids), userids_per_query):
                yield userids[i:i + userids_per_query]

        for userid_chunk in _userid_chunks():
            stories = self.context.graphql_query("bf41e22b1c4ba4c9f31b844ebb7d9056",
                                                 {"reel_ids": userid_chunk, "precomposed_overlay": False})["data"]
            yield from (Story(self.context, media) for media in stories['reels_media'])

    @_requires_login
    def download_stories(self,
                         userids: Optional[List[Union[int, Profile]]] = None,
                         fast_update: bool = False,
                         filename_target: Optional[str] = ':stories',
                         storyitem_filter: Optional[Callable[[StoryItem], bool]] = None) -> None:
        """
        Download available stories from user followees or all stories of users whose ID are given.
        Does not mark stories as seen.
        To use this, one needs to be logged in

        :param userids: List of user IDs or Profiles to be processed in terms of downloading their stories
        :param fast_update: If true, abort when first already-downloaded picture is encountered
        :param filename_target: Replacement for {target} in dirname_pattern and filename_pattern
               or None if profile name should be used instead
        :param storyitem_filter: function(storyitem), which returns True if given StoryItem should be downloaded
        """

        if not userids:
            self.context.log("Retrieving all visible stories...")
        else:
            userids = [p if isinstance(p, int) else p.userid for p in userids]

        for user_story in self.get_stories(userids):
            name = user_story.owner_username
            self.context.log("Retrieving stories from profile {}.".format(name))
            totalcount = user_story.itemcount
            count = 1
            for item in user_story.get_items():
                if storyitem_filter is not None and not storyitem_filter(item):
                    self.context.log("<{} skipped>".format(item), flush=True)
                    continue
                self.context.log("[%3i/%3i] " % (count, totalcount), end="", flush=True)
                count += 1
                with self.context.error_catcher('Download story from user {}'.format(name)):
                    downloaded = self.download_storyitem(item, filename_target if filename_target else name)
                    if fast_update and not downloaded:
                        break

    def download_storyitem(self, item: StoryItem, target: str) -> bool:
        """Download one user story.

        :param item: Story item, as in story['items'] for story in :meth:`get_stories`
        :param target: Replacement for {target} in dirname_pattern and filename_pattern
        :return: True if something was downloaded, False otherwise, i.e. file was already there
        """

        date_local = item.date_local
        dirname = _PostPathFormatter(item).format(self.dirname_pattern, target=target)
        filename = dirname + '/' + self.format_filename(item, target=target)
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        downloaded = False
        if not item.is_video or self.download_video_thumbnails is True:
            url = item.url
            downloaded = self.download_pic(filename=filename, url=url, mtime=date_local)
        if item.is_video and self.download_videos is True:
            downloaded |= self.download_pic(filename=filename, url=item.video_url, mtime=date_local)
        # Save caption if desired
        metadata_string = _ArbitraryItemFormatter(item).format(self.storyitem_metadata_txt_pattern).strip()
        if metadata_string:
            self.save_caption(filename=filename, mtime=item.date_local, caption=metadata_string)
        # Save metadata as JSON if desired.
        if self.save_metadata is not False:
            self.save_metadata_json(filename, item)
        self.context.log()
        return downloaded

    @_requires_login
    def get_highlights(self, user: Union[int, Profile]) -> Iterator[Highlight]:
        """Get all highlights from a user.
        To use this, one needs to be logged in.

        .. versionadded:: 4.1

        :param user: ID or Profile of the user whose highlights should get fetched.
        """

        userid = user if isinstance(user, int) else user.userid
        data = self.context.graphql_query("7c16654f22c819fb63d1183034a5162f",
                                          {"user_id": userid, "include_chaining": False, "include_reel": False,
                                           "include_suggested_users": False, "include_logged_out_extras": False,
                                           "include_highlight_reels": True})["data"]["user"]['edge_highlight_reels']
        if data is None:
            raise BadResponseException('Bad highlights reel JSON.')
        yield from (Highlight(self.context, edge['node'], user if isinstance(user, Profile) else None)
                    for edge in data['edges'])

    @_requires_login
    def download_highlights(self,
                            user: Union[int, Profile],
                            fast_update: bool = False,
                            filename_target: Optional[str] = None,
                            storyitem_filter: Optional[Callable[[StoryItem], bool]] = None) -> None:
        """
        Download available highlights from a user whose ID is given.
        To use this, one needs to be logged in.

        .. versionadded:: 4.1

        :param user: ID or Profile of the user whose highlights should get downloaded.
        :param fast_update: If true, abort when first already-downloaded picture is encountered
        :param filename_target: Replacement for {target} in dirname_pattern and filename_pattern
               or None if profile name and the highlights' titles should be used instead
        :param storyitem_filter: function(storyitem), which returns True if given StoryItem should be downloaded
        """
        for user_highlight in self.get_highlights(user):
            name = user_highlight.owner_username
            self.context.log("Retrieving highlights \"{}\" from profile {}".format(user_highlight.title, name))
            totalcount = user_highlight.itemcount
            count = 1
            for item in user_highlight.get_items():
                if storyitem_filter is not None and not storyitem_filter(item):
                    self.context.log("<{} skipped>".format(item), flush=True)
                    continue
                self.context.log("[%3i/%3i] " % (count, totalcount), end="", flush=True)
                count += 1
                with self.context.error_catcher('Download highlights \"{}\" from user {}'.format(user_highlight.title, name)):
                    downloaded = self.download_storyitem(item, filename_target
                                                         if filename_target
                                                         else '{}/{}'.format(name, user_highlight.title))
                    if fast_update and not downloaded:
                        break

    @_requires_login
    def get_feed_posts(self) -> Iterator[Post]:
        """Get Posts of the user's feed.

        :return: Iterator over Posts of the user's feed.
        """

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
                            post_filter: Optional[Callable[[Post], bool]] = None) -> None:
        """
        Download pictures from the user's feed.

        Example to download up to the 20 pics the user last liked::

            loader = Instaloader()
            loader.load_session_from_file('USER')
            loader.download_feed_posts(max_count=20, fast_update=True,
                                       post_filter=lambda post: post.viewer_has_liked)

        :param max_count: Maximum count of pictures to download
        :param fast_update: If true, abort when first already-downloaded picture is encountered
        :param post_filter: function(post), which returns True if given picture should be downloaded
        """
        self.context.log("Retrieving pictures from your feed...")
        count = 1
        for post in self.get_feed_posts():
            if max_count is not None and count > max_count:
                break
            name = post.owner_username
            if post_filter is not None and not post_filter(post):
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
                             post_filter: Optional[Callable[[Post], bool]] = None) -> None:
        """Download user's saved pictures.

        :param max_count: Maximum count of pictures to download
        :param fast_update: If true, abort when first already-downloaded picture is encountered
        :param post_filter: function(post), which returns True if given picture should be downloaded
        """
        self.context.log("Retrieving saved posts...")
        count = 1
        for post in Profile.from_username(self.context, self.context.username).get_saved_posts():
            if max_count is not None and count > max_count:
                break
            if post_filter is not None and not post_filter(post):
                self.context.log("<{} skipped>".format(post), flush=True)
                continue
            self.context.log("[{:>3}] ".format(count), end=str(), flush=True)
            count += 1
            with self.context.error_catcher('Download saved posts'):
                downloaded = self.download_post(post, target=':saved')
                if fast_update and not downloaded:
                    break

    @_requires_login
    def get_explore_posts(self) -> Iterator[Post]:
        """Get Posts which are worthy of exploring suggested by Instagram.

        :return: Iterator over Posts of the user's suggested posts.
        """
        data = self.context.get_json('explore/', {})
        yield from (Post(self.context, node)
                    for node in self.context.graphql_node_list("df0dcc250c2b18d9fd27c5581ef33c7c",
                                                               {}, 'https://www.instagram.com/explore/',
                                                               lambda d: d['data']['user']['edge_web_discover_media'],
                                                               data['rhx_gis']))

    def get_hashtag_posts(self, hashtag: str) -> Iterator[Post]:
        """Get Posts associated with a #hashtag."""
        has_next_page = True
        end_cursor = None
        while has_next_page:
            if end_cursor:
                params = {'__a': 1, 'max_id': end_cursor}
            else:
                params = {'__a': 1}
            hashtag_data = self.context.get_json('explore/tags/{0}/'.format(hashtag),
                                                 params)['graphql']['hashtag']['edge_hashtag_to_media']
            yield from (Post(self.context, edge['node']) for edge in hashtag_data['edges'])
            has_next_page = hashtag_data['page_info']['has_next_page']
            end_cursor = hashtag_data['page_info']['end_cursor']

    def download_hashtag(self, hashtag: str,
                         max_count: Optional[int] = None,
                         post_filter: Optional[Callable[[Post], bool]] = None,
                         fast_update: bool = False) -> None:
        """Download pictures of one hashtag.

        To download the last 30 pictures with hashtag #cat, do::

            loader = Instaloader()
            loader.download_hashtag('cat', max_count=30)

        :param hashtag: Hashtag to download, without leading '#'
        :param max_count: Maximum count of pictures to download
        :param post_filter: function(post), which returns True if given picture should be downloaded
        :param fast_update: If true, abort when first already-downloaded picture is encountered
        """
        hashtag = hashtag.lower()
        self.context.log("Retrieving pictures with hashtag {}...".format(hashtag))
        count = 1
        for post in self.get_hashtag_posts(hashtag):
            if max_count is not None and count > max_count:
                break
            self.context.log('[{0:3d}] #{1} '.format(count, hashtag), end='', flush=True)
            if post_filter is not None and not post_filter(post):
                self.context.log('<skipped>')
                continue
            count += 1
            with self.context.error_catcher('Download hashtag #{}'.format(hashtag)):
                downloaded = self.download_post(post, target='#' + hashtag)
                if fast_update and not downloaded:
                    break

    def download_tagged(self, profile: Profile, fast_update: bool = False,
                        target: Optional[str] = None,
                        post_filter: Optional[Callable[[Post], bool]] = None) -> None:
        """Download all posts where a profile is tagged.

        .. versionadded:: 4.1"""
        if target is None:
            target = profile.username + '/:tagged'
        self.context.log("Retrieving tagged posts for profile {}.".format(profile.username))
        count = 1
        for post in profile.get_tagged_posts():
            self.context.log("[%3i/???] " % (count), end="", flush=True)
            count += 1
            if post_filter is not None and not post_filter(post):
                self.context.log('<{} skipped>'.format(post))
            with self.context.error_catcher('Download tagged {}'.format(profile.username)):
                downloaded = self.download_post(post, target)
                if fast_update and not downloaded:
                    break

    def _get_id_filename(self, profile_name: str) -> str:
        if ((format_string_contains_key(self.dirname_pattern, 'profile') or
             format_string_contains_key(self.dirname_pattern, 'target'))):
            return '{0}/id'.format(self.dirname_pattern.format(profile=profile_name.lower(),
                                                               target=profile_name.lower()))
        else:
            return '{0}/{1}_id'.format(self.dirname_pattern.format(), profile_name.lower())

    def save_profile_id(self, profile: Profile):
        """
        Store ID of profile locally.

        .. versionadded:: 4.0.6
        """
        os.makedirs(self.dirname_pattern.format(profile=profile.username,
                                                target=profile.username), exist_ok=True)
        with open(self._get_id_filename(profile.username), 'w') as text_file:
            text_file.write(str(profile.userid) + "\n")
            self.context.log("Stored ID {0} for profile {1}.".format(profile.userid, profile.username))

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
        id_filename = self._get_id_filename(profile_name)
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
        except (FileNotFoundError, ValueError):
            pass
        if profile_exists:
            self.save_profile_id(profile)
            return profile
        raise ProfileNotExistsException("Profile {0} does not exist.".format(profile_name))

    def download_profiles(self, profiles: Set[Profile],
                          profile_pic: bool = True, posts: bool = True,
                          tagged: bool = False, highlights: bool = False, stories: bool = False,
                          fast_update: bool = False,
                          post_filter: Optional[Callable[[Post], bool]] = None,
                          storyitem_filter: Optional[Callable[[Post], bool]] = None,
                          raise_errors: bool = False):
        """High-level method to download set of profiles.

        :param profiles: Set of profiles to download.
        :param profile_pic: not :option:`--no-profile-pic`.
        :param posts: not :option:`--no-posts`.
        :param tagged: :option:`--tagged`.
        :param highlights: :option:`--highlights`.
        :param stories: :option:`--stories`.
        :param fast_update: :option:`--fast-update`.
        :param post_filter: :option:`--post-filter`.
        :param storyitem_filter: :option:`--post-filter`.
        :param raise_errors:
           Whether :exc:`LoginRequiredException` and :exc:`PrivateProfileNotFollowedException` should be raised or
           catched and printed with :meth:`InstaloaderContext.error_catcher`.

        .. versionadded:: 4.1"""

        def _error_raiser(_str):
            yield

        error_handler = _error_raiser if raise_errors else self.context.error_catcher

        for profile in profiles:
            with error_handler(profile.username):
                profile_name = profile.username

                # Save metadata as JSON if desired.
                if self.save_metadata:
                    json_filename = '{0}/{1}_{2}'.format(self.dirname_pattern.format(profile=profile_name,
                                                                                     target=profile_name),
                                                         profile_name, profile.userid)
                    self.save_metadata_json(json_filename, profile)

                # Download profile picture
                if profile_pic:
                    with self.context.error_catcher('Download profile picture of {}'.format(profile_name)):
                        self.download_profilepic(profile)

                # Catch some errors
                if profile.is_private:
                    if not self.context.is_logged_in:
                        raise LoginRequiredException("--login=USERNAME required.")
                    if not profile.followed_by_viewer and self.context.username != profile.username:
                        raise PrivateProfileNotFollowedException("Private but not followed.")

                # Download tagged, if requested
                if tagged:
                    with self.context.error_catcher('Download tagged of {}'.format(profile_name)):
                        self.download_tagged(profile, fast_update=fast_update, post_filter=post_filter)

                # Download highlights, if requested
                if highlights:
                    with self.context.error_catcher('Download highlights of {}'.format(profile_name)):
                        self.download_highlights(profile, fast_update=fast_update, storyitem_filter=storyitem_filter)

                # Iterate over pictures and download them
                if posts:
                    self.context.log("Retrieving posts from profile {}.".format(profile_name))
                    totalcount = profile.mediacount
                    count = 1
                    for post in profile.get_posts():
                        self.context.log("[%3i/%3i] " % (count, totalcount), end="", flush=True)
                        count += 1
                        if post_filter is not None and not post_filter(post):
                            self.context.log('<skipped>')
                            continue
                        with self.context.error_catcher("Download {} of {}".format(post, profile_name)):
                            downloaded = self.download_post(post, target=profile_name)
                            if fast_update and not downloaded:
                                break

        if stories and profiles:
            with self.context.error_catcher("Download stories"):
                self.context.log("Downloading stories")
                self.download_stories(userids=list(profiles), fast_update=fast_update, filename_target=None,
                                      storyitem_filter=storyitem_filter)

    def download_profile(self, profile_name: Union[str, Profile],
                         profile_pic: bool = True, profile_pic_only: bool = False,
                         fast_update: bool = False,
                         download_stories: bool = False, download_stories_only: bool = False,
                         download_tagged: bool = False, download_tagged_only: bool = False,
                         post_filter: Optional[Callable[[Post], bool]] = None,
                         storyitem_filter: Optional[Callable[[StoryItem], bool]] = None) -> None:
        """Download one profile

        .. deprecated:: 4.1
           Use :meth:`Instaloader.download_profiles`.
        """

        # Get profile main page json
        # check if profile does exist or name has changed since last download
        # and update name and json data if necessary
        if isinstance(profile_name, str):
            profile = self.check_profile_id(profile_name.lower())
        else:
            profile = profile_name

        profile_name = profile.username

        # Save metadata as JSON if desired.
        if self.save_metadata is not False:
            json_filename = '{0}/{1}_{2}'.format(self.dirname_pattern.format(profile=profile_name, target=profile_name),
                                                 profile_name, profile.userid)
            self.save_metadata_json(json_filename, profile)

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
            if profile.has_viewable_story:
                with self.context.error_catcher("Download stories of {}".format(profile_name)):
                    self.download_stories(userids=[profile.userid], filename_target=profile_name,
                                          fast_update=fast_update, storyitem_filter=storyitem_filter)
            else:
                self.context.log("{} does not have any stories.".format(profile_name))
        if download_stories_only:
            return

        # Download tagged, if requested
        if download_tagged or download_tagged_only:
            with self.context.error_catcher('Download tagged of {}'.format(profile_name)):
                self.download_tagged(profile, fast_update=fast_update, post_filter=post_filter)
        if download_tagged_only:
            return

        # Iterate over pictures and download them
        self.context.log("Retrieving posts from profile {}.".format(profile_name))
        totalcount = profile.mediacount
        count = 1
        for post in profile.get_posts():
            self.context.log("[%3i/%3i] " % (count, totalcount), end="", flush=True)
            count += 1
            if post_filter is not None and not post_filter(post):
                self.context.log('<skipped>')
                continue
            with self.context.error_catcher('Download profile {}'.format(profile_name)):
                downloaded = self.download_post(post, target=profile_name)
                if fast_update and not downloaded:
                    break

    def interactive_login(self, username: str) -> None:
        """Logs in and internally stores session, asking user for password interactively.

        :raises LoginRequiredException: when in quiet mode.
        :raises InvalidArgumentException: If the provided username does not exist.
        :raises ConnectionException: If connection to Instagram failed."""
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
