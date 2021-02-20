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
from hashlib import md5
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, IO, Iterator, List, Optional, Set, Union, cast
from urllib.parse import urlparse

import requests
import urllib3  # type: ignore

from .exceptions import *
from .instaloadercontext import InstaloaderContext, RateController
from .nodeiterator import NodeIterator, resumable_iteration
from .structures import (Hashtag, Highlight, JsonExportable, Post, PostLocation, Profile, Story, StoryItem,
                         load_structure_from_file, save_structure_to_file, PostSidecarNode)


def get_default_session_filename(username: str) -> str:
    """Returns default session filename for given username."""
    sessionfilename = "session-{}".format(username)
    if platform.system() == "Windows":
        # on Windows, use %LOCALAPPDATA%\Instaloader\session-USERNAME
        localappdata = os.getenv("LOCALAPPDATA")
        if localappdata is not None:
            return os.path.join(localappdata, "Instaloader", sessionfilename)
        # legacy fallback - store in temp dir if %LOCALAPPDATA% is not set
        return os.path.join(tempfile.gettempdir(), ".instaloader-" + getpass.getuser(), sessionfilename)
    # on Unix, use ~/.config/instaloader/session-USERNAME
    return os.path.join(os.getenv("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "instaloader", sessionfilename)


def get_legacy_session_filename(username: str) -> str:
    """Returns legacy (until v4.4.3) default session filename for given username."""
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
    return call


def _retry_on_connection_error(func: Callable) -> Callable:
    """Decorator to retry the function max_connection_attemps number of times.

    Herewith-decorated functions need an ``_attempt`` keyword argument.

    This is to decorate functions that do network requests that may fail. Note that
    :meth:`.get_json`, :meth:`.get_iphone_json`, :meth:`.graphql_query` and :meth:`.graphql_node_list` already have
    their own logic for retrying, hence functions that only use these for network access must not be decorated with this
    decorator."""
    @wraps(func)
    def call(instaloader, *args, **kwargs):
        try:
            return func(instaloader, *args, **kwargs)
        except (urllib3.exceptions.HTTPError, requests.exceptions.RequestException, ConnectionException) as err:
            error_string = "{}({}): {}".format(func.__name__, ', '.join([repr(arg) for arg in args]), err)
            if (kwargs.get('_attempt') or 1) == instaloader.context.max_connection_attempts:
                raise ConnectionException(error_string) from None
            instaloader.context.error(error_string + " [retrying; skip with ^C]", repeat_at_end=False)
            try:
                if kwargs.get('_attempt'):
                    kwargs['_attempt'] += 1
                else:
                    kwargs['_attempt'] = 2
                instaloader.context.do_sleep()
                return call(instaloader, *args, **kwargs)
            except KeyboardInterrupt:
                instaloader.context.error("[skipped by user]", repeat_at_end=False)
                raise ConnectionException(error_string) from None
    return call


class _ArbitraryItemFormatter(string.Formatter):
    def __init__(self, item: Any):
        self._item = item

    def get_value(self, key, args, kwargs):
        """Override to substitute {ATTRIBUTE} by attributes of our _item."""
        if key == 'filename' and isinstance(self._item, (Post, StoryItem, PostSidecarNode)):
            return "{filename}"
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
    def get_value(self, key, args, kwargs):
        ret = super().get_value(key, args, kwargs)
        if not isinstance(ret, str):
            return ret
        return self.sanitize_path(ret)

    @staticmethod
    def sanitize_path(ret: str) -> str:
        """Replaces '/' with similar looking Division Slash and some other illegal filename characters on Windows."""
        ret = ret.replace('/', '\u2215')
        if platform.system() == 'Windows':
            ret = ret.replace(':', '\uff1a').replace('<', '\ufe64').replace('>', '\ufe65').replace('\"', '\uff02')
            ret = ret.replace('\\', '\ufe68').replace('|', '\uff5c').replace('?', '\ufe16').replace('*', '\uff0a')
            ret = ret.replace('\n', ' ').replace('\r', ' ')
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
    :param request_timeout: :option:`--request-timeout`, set per-request timeout (seconds)
    :param rate_controller: Generator for a :class:`RateController` to override rate controlling behavior
    :param resume_prefix: :option:`--resume-prefix`, or None for :option:`--no-resume`.
    :param check_resume_bbd: Whether to check the date of expiry of resume files and reject them if expired.
    :param slide: :option:`--slide`

    .. attribute:: context

       The associated :class:`InstaloaderContext` with low-level communication functions and logging.
    """

    def __init__(self,
                 sleep: bool = True,
                 quiet: bool = False,
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
                 max_connection_attempts: int = 3,
                 request_timeout: float = 300.0,
                 rate_controller: Optional[Callable[[InstaloaderContext], RateController]] = None,
                 resume_prefix: Optional[str] = "iterator",
                 check_resume_bbd: bool = True,
                 slide: Optional[str] = None):

        self.context = InstaloaderContext(sleep, quiet, user_agent, max_connection_attempts,
                                          request_timeout, rate_controller)

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
        self.resume_prefix = resume_prefix
        self.check_resume_bbd = check_resume_bbd

        self.slide = slide or ""
        self.slide_start = 0
        self.slide_end = -1
        if self.slide != "":
            splitted = self.slide.split('-')
            if len(splitted) == 1:
                if splitted[0] == 'last':
                    # download only last image of a sidecar
                    self.slide_start = -1
                else:
                    if int(splitted[0]) > 0:
                        self.slide_start = self.slide_end = int(splitted[0])-1
                    else:
                        raise InvalidArgumentException("--slide parameter must be greater than 0.")
            elif len(splitted) == 2:
                if splitted[1] == 'last':
                    self.slide_start = int(splitted[0])-1
                elif 0 < int(splitted[0]) < int(splitted[1]):
                    self.slide_start = int(splitted[0])-1
                    self.slide_end = int(splitted[1])-1
                else:
                    raise InvalidArgumentException("Invalid data for --slide parameter.")
            else:
                raise InvalidArgumentException("Invalid data for --slide parameter.")

    @contextmanager
    def anonymous_copy(self):
        """Yield an anonymous, otherwise equally-configured copy of an Instaloader instance; Then copy its error log."""
        new_loader = Instaloader(
            sleep=self.context.sleep,
            quiet=self.context.quiet,
            user_agent=self.context.user_agent,
            dirname_pattern=self.dirname_pattern,
            filename_pattern=self.filename_pattern,
            download_pictures=self.download_pictures,
            download_videos=self.download_videos,
            download_video_thumbnails=self.download_video_thumbnails,
            download_geotags=self.download_geotags,
            download_comments=self.download_comments,
            save_metadata=self.save_metadata,
            compress_json=self.compress_json,
            post_metadata_txt_pattern=self.post_metadata_txt_pattern,
            storyitem_metadata_txt_pattern=self.storyitem_metadata_txt_pattern,
            max_connection_attempts=self.context.max_connection_attempts,
            request_timeout=self.context.request_timeout,
            resume_prefix=self.resume_prefix,
            check_resume_bbd=self.check_resume_bbd,
            slide=self.slide)
        yield new_loader
        self.context.error_log.extend(new_loader.context.error_log)
        new_loader.context.error_log = []  # avoid double-printing of errors
        new_loader.close()

    def close(self):
        """Close associated session objects and repeat error log."""
        self.context.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @_retry_on_connection_error
    def download_pic(self, filename: str, url: str, mtime: datetime,
                     filename_suffix: Optional[str] = None, _attempt: int = 1) -> bool:
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
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        save_structure_to_file(structure, filename)
        if isinstance(structure, (Post, StoryItem)):
            # log 'json ' message when saving Post or StoryItem
            self.context.log('json', end=' ', flush=True)

    def update_comments(self, filename: str, post: Post) -> None:
        def _postcommentanswer_asdict(comment):
            return {'id': comment.id,
                    'created_at': int(comment.created_at_utc.replace(tzinfo=timezone.utc).timestamp()),
                    'text': comment.text,
                    'owner': comment.owner._asdict(),
                    'likes_count': comment.likes_count}

        def _postcomment_asdict(comment):
            return {**_postcommentanswer_asdict(comment),
                    'answers': sorted([_postcommentanswer_asdict(answer) for answer in comment.answers],
                                      key=lambda t: int(t['id']),
                                      reverse=True)}

        def get_unique_comments(comments, combine_answers=False):
            if not comments:
                return list()
            comments_list = sorted(sorted(list(comments), key=lambda t: int(t['id'])),
                                   key=lambda t: int(t['created_at']), reverse=True)
            unique_comments_list = [comments_list[0]]
            for x, y in zip(comments_list[:-1], comments_list[1:]):
                if x['id'] != y['id']:
                    unique_comments_list.append(y)
                else:
                    unique_comments_list[-1]['likes_count'] = y.get('likes_count')
                    if combine_answers:
                        combined_answers = unique_comments_list[-1].get('answers') or list()
                        if 'answers' in y:
                            combined_answers.extend(y['answers'])
                        unique_comments_list[-1]['answers'] = get_unique_comments(combined_answers)
            return unique_comments_list
        filename += '_comments.json'
        try:
            with open(filename) as fp:
                comments = json.load(fp)
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            comments = list()
        comments.extend(_postcomment_asdict(comment) for comment in post.get_comments())
        if comments:
            comments = get_unique_comments(comments, combine_answers=True)
            answer_ids = set(int(answer['id']) for comment in comments for answer in comment.get('answers', []))
            with open(filename, 'w') as file:
                file.write(json.dumps(list(filter(lambda t: int(t['id']) not in answer_ids, comments)), indent=4))
            self.context.log('comments', end=' ', flush=True)

    def save_caption(self, filename: str, mtime: datetime, caption: str) -> None:
        """Updates picture caption / Post metadata info"""
        def _elliptify(caption):
            pcaption = caption.replace('\n', ' ').strip()
            return '[' + ((pcaption[:29] + u"\u2026") if len(pcaption) > 31 else pcaption) + ']'
        filename += '.txt'
        caption += '\n'
        pcaption = _elliptify(caption)
        bcaption = caption.encode("UTF-8")
        with suppress(FileNotFoundError):
            with open(filename, 'rb') as file:
                file_caption = file.read()
            if file_caption.replace(b'\r\n', b'\n') == bcaption.replace(b'\r\n', b'\n'):
                try:
                    self.context.log(pcaption + ' unchanged', end=' ', flush=True)
                except UnicodeEncodeError:
                    self.context.log('txt unchanged', end=' ', flush=True)
                return None
            else:
                def get_filename(index):
                    return filename if index == 0 else '{0}_old_{2:02}{1}'.format(*os.path.splitext(filename), index)

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
            with BytesIO(bcaption) as bio:
                shutil.copyfileobj(cast(IO, bio), text_file)
        os.utime(filename, (datetime.now().timestamp(), mtime.timestamp()))

    def save_location(self, filename: str, location: PostLocation, mtime: datetime) -> None:
        """Save post location name and Google Maps link."""
        filename += '_location.txt'
        location_string = (location.name + "\n" +
                           "https://maps.google.com/maps?q={0},{1}&ll={0},{1}\n".format(location.lat,
                                                                                        location.lng))
        with open(filename, 'wb') as text_file:
            with BytesIO(location_string.encode()) as bio:
                shutil.copyfileobj(cast(IO, bio), text_file)
        os.utime(filename, (datetime.now().timestamp(), mtime.timestamp()))
        self.context.log('geo', end=' ', flush=True)

    def format_filename_within_target_path(self,
                                           target: Union[str, Path],
                                           owner_profile: Optional[Profile],
                                           identifier: str,
                                           name_suffix: str,
                                           extension: str):
        """Returns a filename within the target path.

        .. versionadded:: 4.5"""
        if ((format_string_contains_key(self.dirname_pattern, 'profile') or
             format_string_contains_key(self.dirname_pattern, 'target'))):
            profile_str = owner_profile.username.lower() if owner_profile is not None else target
            return os.path.join(self.dirname_pattern.format(profile=profile_str, target=target),
                                '{0}_{1}.{2}'.format(identifier, name_suffix, extension))
        else:
            return os.path.join(self.dirname_pattern.format(),
                                '{0}_{1}_{2}.{3}'.format(target, identifier, name_suffix, extension))

    @_retry_on_connection_error
    def download_title_pic(self, url: str, target: Union[str, Path], name_suffix: str, owner_profile: Optional[Profile],
                           _attempt: int = 1) -> None:
        """Downloads and saves a picture that does not have an association with a Post or StoryItem, such as a
        Profile picture or a Highlight cover picture. Modification time is taken from the HTTP response headers.

        .. versionadded:: 4.3"""

        def _epoch_to_string(epoch: datetime) -> str:
            return epoch.strftime('%Y-%m-%d_%H-%M-%S_UTC')

        http_response = self.context.get_raw(url)
        date_object = None  # type: Optional[datetime]
        if 'Last-Modified' in http_response.headers:
            date_object = datetime.strptime(http_response.headers["Last-Modified"], '%a, %d %b %Y %H:%M:%S GMT')
            pic_bytes = None
            pic_identifier = _epoch_to_string(date_object)
        else:
            pic_bytes = http_response.content
            pic_identifier = md5(pic_bytes).hexdigest()[:16]
        filename = self.format_filename_within_target_path(target, owner_profile, pic_identifier, name_suffix, 'jpg')
        content_length = http_response.headers.get('Content-Length', None)
        if os.path.isfile(filename) and (not self.context.is_logged_in or
                                         (content_length is not None and
                                          os.path.getsize(filename) >= int(content_length))):
            self.context.log(filename + ' already exists')
            return None
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        self.context.write_raw(pic_bytes if pic_bytes else http_response, filename)
        if date_object:
            os.utime(filename, (datetime.now().timestamp(), date_object.timestamp()))
        self.context.log('')  # log output of _get_and_write_raw() does not produce \n

    def download_profilepic(self, profile: Profile) -> None:
        """Downloads and saves profile pic."""
        self.download_title_pic(profile.profile_pic_url, profile.username.lower(), 'profile_pic', profile)

    def download_highlight_cover(self, highlight: Highlight, target: Union[str, Path]) -> None:
        """Downloads and saves Highlight cover picture.

        .. versionadded:: 4.3"""
        self.download_title_pic(highlight.cover_url, target, 'cover', highlight.owner_profile)

    def download_hashtag_profilepic(self, hashtag: Hashtag) -> None:
        """Downloads and saves the profile picture of a Hashtag.

        .. versionadded:: 4.4"""
        self.download_title_pic(hashtag.profile_pic_url, '#' + hashtag.name, 'profile_pic', None)

    @_requires_login
    def save_session_to_file(self, filename: Optional[str] = None) -> None:
        """Saves internally stored :class:`requests.Session` object.

        :param filename: Filename, or None to use default filename.
        :raises LoginRequiredException: If called without being logged in.
        """
        if filename is None:
            assert self.context.username is not None
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
            if not os.path.exists(filename):
                filename = get_legacy_session_filename(username)
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
        :raises ConnectionException: If connection to Instagram failed.
        :raises TwoFactorAuthRequiredException: First step of 2FA login done, now call
           :meth:`Instaloader.two_factor_login`."""
        self.context.login(user, passwd)

    def two_factor_login(self, two_factor_code) -> None:
        """Second step of login if 2FA is enabled.
        Not meant to be used directly, use :meth:`Instaloader.two_factor_login`.

        :raises InvalidArgumentException: No two-factor authentication pending.
        :raises BadCredentialsException: 2FA verification code invalid.

        .. versionadded:: 4.2"""
        self.context.two_factor_login(two_factor_code)

    @staticmethod
    def __prepare_filename(filename_template: str, url: Callable[[], str]) -> str:
        """Replace filename token inside filename_template with url's filename and assure the directories exist.

        .. versionadded:: 4.6"""
        if "{filename}" in filename_template:
            filename = filename_template.replace("{filename}",
                                                 os.path.splitext(os.path.basename(urlparse(url()).path))[0])
        else:
            filename = filename_template
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        return filename

    def format_filename(self, item: Union[Post, StoryItem, PostSidecarNode], target: Optional[Union[str, Path]] = None):
        """Format filename of a :class:`Post` or :class:`StoryItem` according to ``filename-pattern`` parameter.

        .. versionadded:: 4.1"""
        return _PostPathFormatter(item).format(self.filename_pattern, target=target)

    def download_post(self, post: Post, target: Union[str, Path]) -> bool:
        """
        Download everything associated with one instagram post node, i.e. picture, caption and video.

        :param post: Post to download.
        :param target: Target name, i.e. profile name, #hashtag, :feed; for filename.
        :return: True if something was downloaded, False otherwise, i.e. file was already there
        """

        dirname = _PostPathFormatter(post).format(self.dirname_pattern, target=target)
        filename_template = os.path.join(dirname, self.format_filename(post, target=target))
        filename = self.__prepare_filename(filename_template, lambda: post.url)

        # Download the image(s) / video thumbnail and videos within sidecars if desired
        downloaded = True
        if post.typename == 'GraphSidecar':
            if self.download_pictures or self.download_videos:
                for edge_number, sidecar_node in enumerate(
                        post.get_sidecar_nodes(self.slide_start, self.slide_end),
                        start=post.mediacount if self.slide_start < 0 else self.slide_start + 1
                ):
                    suffix = str(edge_number)  # type: Optional[str]
                    if '{filename}' in self.filename_pattern:
                        suffix = None
                    if self.download_pictures and (not sidecar_node.is_video or self.download_video_thumbnails):
                        # pylint:disable=cell-var-from-loop
                        sidecar_filename = self.__prepare_filename(filename_template, lambda: sidecar_node.display_url)
                        # Download sidecar picture or video thumbnail (--no-pictures implies --no-video-thumbnails)
                        downloaded &= self.download_pic(filename=sidecar_filename, url=sidecar_node.display_url,
                                                        mtime=post.date_local, filename_suffix=suffix)
                    if sidecar_node.is_video and self.download_videos:
                        # pylint:disable=cell-var-from-loop
                        sidecar_filename = self.__prepare_filename(filename_template, lambda: sidecar_node.video_url)
                        # Download sidecar video if desired
                        downloaded &= self.download_pic(filename=sidecar_filename, url=sidecar_node.video_url,
                                                        mtime=post.date_local, filename_suffix=suffix)
        elif post.typename == 'GraphImage':
            # Download picture
            if self.download_pictures:
                downloaded = self.download_pic(filename=filename, url=post.url, mtime=post.date_local)
        elif post.typename == 'GraphVideo':
            # Download video thumbnail (--no-pictures implies --no-video-thumbnails)
            if self.download_pictures and self.download_video_thumbnails:
                with self.context.error_catcher("Video thumbnail of {}".format(post)):
                    downloaded = self.download_pic(filename=filename, url=post.url, mtime=post.date_local)
        else:
            self.context.error("Warning: {0} has unknown typename: {1}".format(post, post.typename))

        # Save caption if desired
        metadata_string = _ArbitraryItemFormatter(post).format(self.post_metadata_txt_pattern).strip()
        if metadata_string:
            self.save_caption(filename=filename, mtime=post.date_local, caption=metadata_string)

        # Download video if desired
        if post.is_video and self.download_videos:
            downloaded &= self.download_pic(filename=filename, url=post.video_url, mtime=post.date_local)

        # Download geotags if desired
        if self.download_geotags and post.location:
            self.save_location(filename, post.location, post.date_local)

        # Update comments if desired
        if self.download_comments:
            self.update_comments(filename=filename, post=post)

        # Save metadata as JSON if desired.
        if self.save_metadata:
            self.save_metadata_json(filename, post)

        self.context.log()
        return downloaded

    @_requires_login
    def get_stories(self, userids: Optional[List[int]] = None) -> Iterator[Story]:
        """Get available stories from followees or all stories of users whose ID are given.
        Does not mark stories as seen.
        To use this, one needs to be logged in

        :param userids: List of user IDs to be processed in terms of downloading their stories, or None.
        :raises LoginRequiredException: If called without being logged in.
        """

        if not userids:
            data = self.context.graphql_query("d15efd8c0c5b23f0ef71f18bf363c704",
                                              {"only_stories": True})["data"]["user"]
            if data is None:
                raise BadResponseException('Bad stories reel JSON.')
            userids = list(edge["node"]["id"] for edge in data["feed_reels_tray"]["edge_reels_tray_to_reel"]["edges"])

        def _userid_chunks():
            assert userids is not None
            userids_per_query = 50
            for i in range(0, len(userids), userids_per_query):
                yield userids[i:i + userids_per_query]

        for userid_chunk in _userid_chunks():
            stories = self.context.graphql_query("303a4ae99711322310f25250d988f3b7",
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
        :raises LoginRequiredException: If called without being logged in.
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

    def download_storyitem(self, item: StoryItem, target: Union[str, Path]) -> bool:
        """Download one user story.

        :param item: Story item, as in story['items'] for story in :meth:`get_stories`
        :param target: Replacement for {target} in dirname_pattern and filename_pattern
        :return: True if something was downloaded, False otherwise, i.e. file was already there
        """

        date_local = item.date_local
        dirname = _PostPathFormatter(item).format(self.dirname_pattern, target=target)
        filename_template = os.path.join(dirname, self.format_filename(item, target=target))
        filename = self.__prepare_filename(filename_template, lambda: item.url)
        downloaded = False
        if not item.is_video or self.download_video_thumbnails is True:
            url = item.url
            downloaded = self.download_pic(filename=filename, url=url, mtime=date_local)
        if item.is_video and self.download_videos is True:
            filename = self.__prepare_filename(filename_template, lambda: str(item.video_url))
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
        :raises LoginRequiredException: If called without being logged in.
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

        .. versionchanged:: 4.3
           Also downloads and saves the Highlight's cover pictures.

        :param user: ID or Profile of the user whose highlights should get downloaded.
        :param fast_update: If true, abort when first already-downloaded picture is encountered
        :param filename_target: Replacement for {target} in dirname_pattern and filename_pattern
               or None if profile name and the highlights' titles should be used instead
        :param storyitem_filter: function(storyitem), which returns True if given StoryItem should be downloaded
        :raises LoginRequiredException: If called without being logged in.
        """
        for user_highlight in self.get_highlights(user):
            name = user_highlight.owner_username
            highlight_target = (filename_target
                                if filename_target
                                else (Path(_PostPathFormatter.sanitize_path(name)) /
                                      _PostPathFormatter.sanitize_path(user_highlight.title)))  # type: Union[str, Path]
            self.context.log("Retrieving highlights \"{}\" from profile {}".format(user_highlight.title, name))
            self.download_highlight_cover(user_highlight, highlight_target)
            totalcount = user_highlight.itemcount
            count = 1
            for item in user_highlight.get_items():
                if storyitem_filter is not None and not storyitem_filter(item):
                    self.context.log("<{} skipped>".format(item), flush=True)
                    continue
                self.context.log("[%3i/%3i] " % (count, totalcount), end="", flush=True)
                count += 1
                with self.context.error_catcher('Download highlights \"{}\" from user {}'.format(user_highlight.title,
                                                                                                 name)):
                    downloaded = self.download_storyitem(item, highlight_target)
                    if fast_update and not downloaded:
                        break

    def posts_download_loop(self,
                            posts: Iterator[Post],
                            target: Union[str, Path],
                            fast_update: bool = False,
                            post_filter: Optional[Callable[[Post], bool]] = None,
                            max_count: Optional[int] = None,
                            total_count: Optional[int] = None,
                            owner_profile: Optional[Profile] = None) -> None:
        """
        Download the Posts returned by given Post Iterator.

        .. versionadded:: 4.4

        .. versionchanged:: 4.5
           Transparently resume an aborted operation if `posts` is a :class:`NodeIterator`.

        :param posts: Post Iterator to loop through.
        :param target: Target name.
        :param fast_update: :option:`--fast-update`.
        :param post_filter: :option:`--post-filter`.
        :param max_count: Maximum count of Posts to download (:option:`--count`).
        :param total_count: Total number of posts returned by given iterator.
        :param owner_profile: Associated profile, if any.
        """
        displayed_count = (max_count if total_count is None or max_count is not None and max_count < total_count
                           else total_count)
        sanitized_target = target
        if isinstance(target, str):
            sanitized_target = _PostPathFormatter.sanitize_path(target)
        with resumable_iteration(
                context=self.context,
                iterator=posts,
                load=load_structure_from_file,
                save=save_structure_to_file,
                format_path=lambda magic: self.format_filename_within_target_path(
                    sanitized_target, owner_profile, self.resume_prefix or '', magic, 'json.xz'
                ),
                check_bbd=self.check_resume_bbd,
                enabled=self.resume_prefix is not None
        ) as (is_resuming, start_index):
            for number, post in enumerate(posts, start=start_index + 1):
                if max_count is not None and number > max_count:
                    break
                if displayed_count is not None:
                    self.context.log("[{0:{w}d}/{1:{w}d}] ".format(number, displayed_count,
                                                                   w=len(str(displayed_count))),
                                     end="", flush=True)
                else:
                    self.context.log("[{:3d}] ".format(number), end="", flush=True)
                if post_filter is not None:
                    try:
                        if not post_filter(post):
                            self.context.log("{} skipped".format(post))
                            continue
                    except (InstaloaderException, KeyError, TypeError) as err:
                        self.context.error("{} skipped. Filter evaluation failed: {}".format(post, err))
                        continue
                with self.context.error_catcher("Download {} of {}".format(post, target)):
                    # The PostChangedException gets raised if the Post's id/shortcode changed while obtaining
                    # additional metadata. This is most likely the case if a HTTP redirect takes place while
                    # resolving the shortcode URL.
                    # The `post_changed` variable keeps the fast-update functionality alive: A Post which is
                    # obained after a redirect has probably already been downloaded as a previous Post of the
                    # same Profile.
                    # Observed in issue #225: https://github.com/instaloader/instaloader/issues/225
                    post_changed = False
                    while True:
                        try:
                            downloaded = self.download_post(post, target=target)
                            break
                        except PostChangedException:
                            post_changed = True
                            continue
                    if fast_update and not downloaded and not post_changed:
                        # disengage fast_update for first post when resuming
                        if not is_resuming or number > 0:
                            break

    @_requires_login
    def get_feed_posts(self) -> Iterator[Post]:
        """Get Posts of the user's feed.

        :return: Iterator over Posts of the user's feed.
        :raises LoginRequiredException: If called without being logged in.
        """

        data = self.context.graphql_query("d6f4427fbe92d846298cf93df0b937d3", {})["data"]

        while True:
            feed = data["user"]["edge_web_feed_timeline"]
            for edge in feed["edges"]:
                node = edge["node"]
                if node.get("__typename") in Post.supported_graphql_types() and node.get("shortcode") is not None:
                    yield Post(self.context, node)
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
        :raises LoginRequiredException: If called without being logged in.
        """
        self.context.log("Retrieving pictures from your feed...")
        self.posts_download_loop(self.get_feed_posts(), ":feed", fast_update, post_filter, max_count=max_count)

    @_requires_login
    def download_saved_posts(self, max_count: int = None, fast_update: bool = False,
                             post_filter: Optional[Callable[[Post], bool]] = None) -> None:
        """Download user's saved pictures.

        :param max_count: Maximum count of pictures to download
        :param fast_update: If true, abort when first already-downloaded picture is encountered
        :param post_filter: function(post), which returns True if given picture should be downloaded
        :raises LoginRequiredException: If called without being logged in.
        """
        self.context.log("Retrieving saved posts...")
        assert self.context.username is not None  # safe due to @_requires_login; required by typechecker
        node_iterator = Profile.own_profile(self.context).get_saved_posts()
        self.posts_download_loop(node_iterator, ":saved",
                                 fast_update, post_filter,
                                 max_count=max_count, total_count=node_iterator.count)

    @_requires_login
    def get_location_posts(self, location: str) -> Iterator[Post]:
        """Get Posts which are listed by Instagram for a given Location.

        :return:  Iterator over Posts of a location's posts
        :raises LoginRequiredException: If called without being logged in.

        .. versionadded:: 4.2

        .. versionchanged:: 4.2.9
           Require being logged in (as required by Instagram)
        """
        has_next_page = True
        end_cursor = None
        while has_next_page:
            if end_cursor:
                params = {'__a': 1, 'max_id': end_cursor}
            else:
                params = {'__a': 1}
            location_data = self.context.get_json('explore/locations/{0}/'.format(location),
                                                  params)['graphql']['location']['edge_location_to_media']
            yield from (Post(self.context, edge['node']) for edge in location_data['edges'])
            has_next_page = location_data['page_info']['has_next_page']
            end_cursor = location_data['page_info']['end_cursor']

    @_requires_login
    def download_location(self, location: str,
                          max_count: Optional[int] = None,
                          post_filter: Optional[Callable[[Post], bool]] = None,
                          fast_update: bool = False) -> None:
        """Download pictures of one location.

        To download the last 30 pictures with location 362629379, do::

            loader = Instaloader()
            loader.download_location(362629379, max_count=30)

        :param location: Location to download, as Instagram numerical ID
        :param max_count: Maximum count of pictures to download
        :param post_filter: function(post), which returns True if given picture should be downloaded
        :param fast_update: If true, abort when first already-downloaded picture is encountered
        :raises LoginRequiredException: If called without being logged in.

        .. versionadded:: 4.2

        .. versionchanged:: 4.2.9
           Require being logged in (as required by Instagram)
        """
        self.context.log("Retrieving pictures for location {}...".format(location))
        self.posts_download_loop(self.get_location_posts(location), "%" + location, fast_update, post_filter,
                                 max_count=max_count)

    @_requires_login
    def get_explore_posts(self) -> NodeIterator[Post]:
        """Get Posts which are worthy of exploring suggested by Instagram.

        :return: Iterator over Posts of the user's suggested posts.
        :rtype: NodeIterator[Post]
        :raises LoginRequiredException: If called without being logged in.
        """
        return NodeIterator(
            self.context,
            'df0dcc250c2b18d9fd27c5581ef33c7c',
            lambda d: d['data']['user']['edge_web_discover_media'],
            lambda n: Post(self.context, n),
            query_referer='https://www.instagram.com/explore/',
        )

    def get_hashtag_posts(self, hashtag: str) -> Iterator[Post]:
        """Get Posts associated with a #hashtag.

        .. deprecated:: 4.4
           Use :meth:`Hashtag.get_posts`."""
        return Hashtag.from_name(self.context, hashtag).get_posts()

    def download_hashtag(self, hashtag: Union[Hashtag, str],
                         max_count: Optional[int] = None,
                         post_filter: Optional[Callable[[Post], bool]] = None,
                         fast_update: bool = False,
                         profile_pic: bool = True,
                         posts: bool = True) -> None:
        """Download pictures of one hashtag.

        To download the last 30 pictures with hashtag #cat, do::

            loader = Instaloader()
            loader.download_hashtag('cat', max_count=30)

        :param hashtag: Hashtag to download, as instance of :class:`Hashtag`, or string without leading '#'
        :param max_count: Maximum count of pictures to download
        :param post_filter: function(post), which returns True if given picture should be downloaded
        :param fast_update: If true, abort when first already-downloaded picture is encountered
        :param profile_pic: not :option:`--no-profile-pic`.
        :param posts: not :option:`--no-posts`.

        .. versionchanged:: 4.4
           Add parameters `profile_pic` and `posts`.
        """
        if isinstance(hashtag, str):
            with self.context.error_catcher("Get hashtag #{}".format(hashtag)):
                hashtag = Hashtag.from_name(self.context, hashtag)
        if not isinstance(hashtag, Hashtag):
            return
        target = "#" + hashtag.name
        if profile_pic:
            with self.context.error_catcher("Download profile picture of {}".format(target)):
                self.download_hashtag_profilepic(hashtag)
        if posts:
            self.context.log("Retrieving pictures with hashtag #{}...".format(hashtag.name))
            self.posts_download_loop(hashtag.get_all_posts(), target, fast_update, post_filter,
                                     max_count=max_count)
        if self.save_metadata:
            json_filename = '{0}/{1}'.format(self.dirname_pattern.format(profile=target,
                                                                         target=target),
                                             target)
            self.save_metadata_json(json_filename, hashtag)

    def download_tagged(self, profile: Profile, fast_update: bool = False,
                        target: Optional[str] = None,
                        post_filter: Optional[Callable[[Post], bool]] = None) -> None:
        """Download all posts where a profile is tagged.

        .. versionadded:: 4.1"""
        self.context.log("Retrieving tagged posts for profile {}.".format(profile.username))
        self.posts_download_loop(profile.get_tagged_posts(),
                                 target if target
                                 else (Path(_PostPathFormatter.sanitize_path(profile.username)) /
                                       _PostPathFormatter.sanitize_path(':tagged')),
                                 fast_update, post_filter)

    def download_igtv(self, profile: Profile, fast_update: bool = False,
                      post_filter: Optional[Callable[[Post], bool]] = None) -> None:
        """Download IGTV videos of a profile.

        .. versionadded:: 4.3"""
        self.context.log("Retrieving IGTV videos for profile {}.".format(profile.username))
        self.posts_download_loop(profile.get_igtv_posts(), profile.username, fast_update, post_filter,
                                 total_count=profile.igtvcount, owner_profile=profile)

    def _get_id_filename(self, profile_name: str) -> str:
        if ((format_string_contains_key(self.dirname_pattern, 'profile') or
             format_string_contains_key(self.dirname_pattern, 'target'))):
            return os.path.join(self.dirname_pattern.format(profile=profile_name.lower(),
                                                            target=profile_name.lower()),
                                'id')
        else:
            return os.path.join(self.dirname_pattern.format(),
                                '{0}_id'.format(profile_name.lower()))

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
        profile_name_not_exists_err = None
        try:
            profile = Profile.from_username(self.context, profile_name)
        except ProfileNotExistsException as err:
            profile_name_not_exists_err = err
        id_filename = self._get_id_filename(profile_name)
        try:
            with open(id_filename, 'rb') as id_file:
                profile_id = int(id_file.read())
            if (profile is None) or \
                    (profile_id != profile.userid):
                if profile is not None:
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
            # profile exists and profile id matches saved id
            return profile
        except (FileNotFoundError, ValueError):
            pass
        if profile is not None:
            self.save_profile_id(profile)
            return profile
        if profile_name_not_exists_err:
            raise profile_name_not_exists_err
        raise ProfileNotExistsException("Profile {0} does not exist.".format(profile_name))

    def download_profiles(self, profiles: Set[Profile],
                          profile_pic: bool = True, posts: bool = True,
                          tagged: bool = False,
                          igtv: bool = False,
                          highlights: bool = False,
                          stories: bool = False,
                          fast_update: bool = False,
                          post_filter: Optional[Callable[[Post], bool]] = None,
                          storyitem_filter: Optional[Callable[[Post], bool]] = None,
                          raise_errors: bool = False):
        """High-level method to download set of profiles.

        :param profiles: Set of profiles to download.
        :param profile_pic: not :option:`--no-profile-pic`.
        :param posts: not :option:`--no-posts`.
        :param tagged: :option:`--tagged`.
        :param igtv: :option:`--igtv`.
        :param highlights: :option:`--highlights`.
        :param stories: :option:`--stories`.
        :param fast_update: :option:`--fast-update`.
        :param post_filter: :option:`--post-filter`.
        :param storyitem_filter: :option:`--post-filter`.
        :param raise_errors:
           Whether :exc:`LoginRequiredException` and :exc:`PrivateProfileNotFollowedException` should be raised or
           catched and printed with :meth:`InstaloaderContext.error_catcher`.

        .. versionadded:: 4.1

        .. versionchanged:: 4.3
           Add `igtv` parameter.
        """

        @contextmanager
        def _error_raiser(_str):
            yield

        # error_handler type is Callable[[Optional[str]], ContextManager[None]] (not supported with Python 3.5.0..3.5.3)
        error_handler = _error_raiser if raise_errors else self.context.error_catcher

        for profile in profiles:
            with error_handler(profile.username):  # type: ignore # (ignore type for Python 3.5 support)
                profile_name = profile.username

                # Download profile picture
                if profile_pic:
                    with self.context.error_catcher('Download profile picture of {}'.format(profile_name)):
                        self.download_profilepic(profile)

                # Save metadata as JSON if desired.
                if self.save_metadata:
                    json_filename = os.path.join(self.dirname_pattern.format(profile=profile_name,
                                                                             target=profile_name),
                                                 '{0}_{1}'.format(profile_name, profile.userid))
                    self.save_metadata_json(json_filename, profile)

                # Catch some errors
                if tagged or igtv or highlights or posts:
                    if (not self.context.is_logged_in and
                            profile.is_private):
                        raise LoginRequiredException("--login=USERNAME required.")
                    if (self.context.username != profile.username and
                            profile.is_private and
                            not profile.followed_by_viewer):
                        raise PrivateProfileNotFollowedException("Private but not followed.")

                # Download tagged, if requested
                if tagged:
                    with self.context.error_catcher('Download tagged of {}'.format(profile_name)):
                        self.download_tagged(profile, fast_update=fast_update, post_filter=post_filter)

                # Download IGTV, if requested
                if igtv:
                    with self.context.error_catcher('Download IGTV of {}'.format(profile_name)):
                        self.download_igtv(profile, fast_update=fast_update, post_filter=post_filter)

                # Download highlights, if requested
                if highlights:
                    with self.context.error_catcher('Download highlights of {}'.format(profile_name)):
                        self.download_highlights(profile, fast_update=fast_update, storyitem_filter=storyitem_filter)

                # Iterate over pictures and download them
                if posts:
                    self.context.log("Retrieving posts from profile {}.".format(profile_name))
                    self.posts_download_loop(profile.get_posts(), profile_name, fast_update, post_filter,
                                             total_count=profile.mediacount, owner_profile=profile)

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
        self.posts_download_loop(profile.get_posts(), profile_name, fast_update, post_filter,
                                 total_count=profile.mediacount, owner_profile=profile)

    def interactive_login(self, username: str) -> None:
        """Logs in and internally stores session, asking user for password interactively.

        :raises LoginRequiredException: when in quiet mode.
        :raises InvalidArgumentException: If the provided username does not exist.
        :raises ConnectionException: If connection to Instagram failed."""
        if self.context.quiet:
            raise LoginRequiredException("Quiet mode requires given password or valid session file.")
        try:
            password = None
            while password is None:
                password = getpass.getpass(prompt="Enter Instagram password for %s: " % username)
                try:
                    self.login(username, password)
                except BadCredentialsException as err:
                    print(err, file=sys.stderr)
                    password = None
        except TwoFactorAuthRequiredException:
            while True:
                try:
                    code = input("Enter 2FA verification code: ")
                    self.two_factor_login(code)
                    break
                except BadCredentialsException:
                    pass
