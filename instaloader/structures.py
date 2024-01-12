import json
import lzma
import re
from base64 import b64decode, b64encode
from contextlib import suppress
from datetime import datetime
from itertools import islice
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Iterator, List, NamedTuple, Optional, Tuple, Union
from unicodedata import normalize

from . import __version__
from .exceptions import *
from .instaloadercontext import InstaloaderContext
from .nodeiterator import FrozenNodeIterator, NodeIterator
from .sectioniterator import SectionIterator


class PostSidecarNode(NamedTuple):
    """Item of a Sidecar Post."""
    is_video: bool
    display_url: str
    video_url: str


PostSidecarNode.is_video.__doc__ = "Whether this node is a video."
PostSidecarNode.display_url.__doc__ = "URL of image or video thumbnail."
PostSidecarNode.video_url.__doc__ = "URL of video or None."


class PostCommentAnswer(NamedTuple):
    id: int
    created_at_utc: datetime
    text: str
    owner: 'Profile'
    likes_count: int


PostCommentAnswer.id.__doc__ = "ID number of comment."
PostCommentAnswer.created_at_utc.__doc__ = ":class:`~datetime.datetime` when comment was created (UTC)."
PostCommentAnswer.text.__doc__ = "Comment text."
PostCommentAnswer.owner.__doc__ = "Owner :class:`Profile` of the comment."
PostCommentAnswer.likes_count.__doc__ = "Number of likes on comment."


class PostComment(NamedTuple):
    id: int
    created_at_utc: datetime
    text: str
    owner: 'Profile'
    likes_count: int
    answers: Iterator[PostCommentAnswer]


for field in PostCommentAnswer._fields:
    getattr(PostComment, field).__doc__ = getattr(PostCommentAnswer, field).__doc__  # pylint: disable=no-member
PostComment.answers.__doc__ = r"Iterator which yields all :class:`PostCommentAnswer`\ s for the comment."


class PostLocation(NamedTuple):
    id: int
    name: str
    slug: str
    has_public_page: Optional[bool]
    lat: Optional[float]
    lng: Optional[float]


PostLocation.id.__doc__ = "ID number of location."
PostLocation.name.__doc__ = "Location name."
PostLocation.slug.__doc__ = "URL friendly variant of location name."
PostLocation.has_public_page.__doc__ = "Whether location has a public page."
PostLocation.lat.__doc__ = "Latitude (:class:`float` or None)."
PostLocation.lng.__doc__ = "Longitude (:class:`float` or None)."

# This regular expression is by MiguelX413
_hashtag_regex = re.compile(r"(?:#)((?:\w){1,150})")

# This regular expression is modified from jStassen, adjusted to use Python's \w to
# support Unicode and a word/beginning of string delimiter at the beginning to ensure
# that no email addresses join the list of mentions.
# http://blog.jstassen.com/2016/03/code-regex-for-instagram-username-and-hashtags/
_mention_regex = re.compile(r"(?:^|[^\w\n]|_)(?:@)(\w(?:(?:\w|(?:\.(?!\.))){0,28}(?:\w))?)", re.ASCII)


def _optional_normalize(string: Optional[str]) -> Optional[str]:
    if string is not None:
        return normalize("NFC", string)
    else:
        return None


class Post:
    """
    Structure containing information about an Instagram post.

    Created by methods :meth:`Profile.get_posts`, :meth:`Instaloader.get_hashtag_posts`,
    :meth:`Instaloader.get_feed_posts` and :meth:`Profile.get_saved_posts`, which return iterators of Posts::

       L = Instaloader()
       for post in L.get_hashtag_posts(HASHTAG):
           L.download_post(post, target='#'+HASHTAG)

    Might also be created with::

       post = Post.from_shortcode(L.context, SHORTCODE)

    This class unifies access to the properties associated with a post. It implements == and is
    hashable.

    :param context: :attr:`Instaloader.context` used for additional queries if neccessary..
    :param node: Node structure, as returned by Instagram.
    :param owner_profile: The Profile of the owner, if already known at creation.
    """

    def __init__(self, context: InstaloaderContext, node: Dict[str, Any],
                 owner_profile: Optional['Profile'] = None):
        assert 'shortcode' in node or 'code' in node

        self._context = context
        self._node = node
        self._owner_profile = owner_profile
        self._full_metadata_dict: Optional[Dict[str, Any]] = None
        self._location: Optional[PostLocation] = None
        self._iphone_struct_ = None
        if 'iphone_struct' in node:
            # if loaded from JSON with load_structure_from_file()
            self._iphone_struct_ = node['iphone_struct']

    @classmethod
    def from_shortcode(cls, context: InstaloaderContext, shortcode: str):
        """Create a post object from a given shortcode"""
        # pylint:disable=protected-access
        post = cls(context, {'shortcode': shortcode})
        post._node = post._full_metadata
        return post

    @classmethod
    def from_mediaid(cls, context: InstaloaderContext, mediaid: int):
        """Create a post object from a given mediaid"""
        return cls.from_shortcode(context, Post.mediaid_to_shortcode(mediaid))

    @classmethod
    def from_iphone_struct(cls, context: InstaloaderContext, media: Dict[str, Any]):
        """Create a post from a given iphone_struct.

        .. versionadded:: 4.9"""
        media_types = {
            1: "GraphImage",
            2: "GraphVideo",
            8: "GraphSidecar",
        }
        fake_node = {
            "shortcode": media["code"],
            "id": media["pk"],
            "__typename": media_types[media["media_type"]],
            "is_video": media_types[media["media_type"]] == "GraphVideo",
            "date": media["taken_at"],
            "caption": media["caption"].get("text") if media.get("caption") is not None else None,
            "title": media.get("title"),
            "viewer_has_liked": media["has_liked"],
            "edge_media_preview_like": {"count": media["like_count"]},
            "iphone_struct": media,
        }
        with suppress(KeyError):
            fake_node["display_url"] = media['image_versions2']['candidates'][0]['url']
        with suppress(KeyError):
            fake_node["video_url"] = media['video_versions'][-1]['url']
            fake_node["video_duration"] = media["video_duration"]
            fake_node["video_view_count"] = media["view_count"]
        with suppress(KeyError):
            fake_node["edge_sidecar_to_children"] = {"edges": [{"node": {
                "display_url": node['image_versions2']['candidates'][0]['url'],
                "is_video": media_types[node["media_type"]] == "GraphVideo",
            }} for node in media["carousel_media"]]}
        return cls(context, fake_node, Profile.from_iphone_struct(context, media["user"]) if "user" in media else None)

    @staticmethod
    def shortcode_to_mediaid(code: str) -> int:
        if len(code) > 11:
            raise InvalidArgumentException("Wrong shortcode \"{0}\", unable to convert to mediaid.".format(code))
        code = 'A' * (12 - len(code)) + code
        return int.from_bytes(b64decode(code.encode(), b'-_'), 'big')

    @staticmethod
    def mediaid_to_shortcode(mediaid: int) -> str:
        if mediaid.bit_length() > 64:
            raise InvalidArgumentException("Wrong mediaid {0}, unable to convert to shortcode".format(str(mediaid)))
        return b64encode(mediaid.to_bytes(9, 'big'), b'-_').decode().replace('A', ' ').lstrip().replace(' ', 'A')

    @staticmethod
    def supported_graphql_types() -> List[str]:
        """The values of __typename fields that the :class:`Post` class can handle."""
        return ["GraphImage", "GraphVideo", "GraphSidecar"]

    def _asdict(self):
        node = self._node
        if self._full_metadata_dict:
            node.update(self._full_metadata_dict)
        if self._owner_profile:
            node['owner'] = self.owner_profile._asdict()
        if self._location:
            node['location'] = self._location._asdict()
        if self._iphone_struct_:
            node['iphone_struct'] = self._iphone_struct_
        return node

    @property
    def shortcode(self) -> str:
        """Media shortcode. URL of the post is instagram.com/p/<shortcode>/."""
        return self._node['shortcode'] if 'shortcode' in self._node else self._node['code']

    @property
    def mediaid(self) -> int:
        """The mediaid is a decimal representation of the media shortcode."""
        return int(self._node['id'])

    @property
    def title(self) -> Optional[str]:
        """Title of post"""
        try:
            return self._field('title')
        except KeyError:
            return None

    def __repr__(self):
        return '<Post {}>'.format(self.shortcode)

    def __eq__(self, o: object) -> bool:
        if isinstance(o, Post):
            return self.shortcode == o.shortcode
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.shortcode)

    def _obtain_metadata(self):
        if not self._full_metadata_dict:
            pic_json = self._context.graphql_query(
                '2b0673e0dc4580674a88d426fe00ea90',
                {'shortcode': self.shortcode}
            )
            self._full_metadata_dict = pic_json['data']['shortcode_media']
            if self._full_metadata_dict is None:
                raise BadResponseException("Fetching Post metadata failed.")
            if self.shortcode != self._full_metadata_dict['shortcode']:
                self._node.update(self._full_metadata_dict)
                raise PostChangedException

    @property
    def _full_metadata(self) -> Dict[str, Any]:
        self._obtain_metadata()
        assert self._full_metadata_dict is not None
        return self._full_metadata_dict

    @property
    def _iphone_struct(self) -> Dict[str, Any]:
        if not self._context.iphone_support:
            raise IPhoneSupportDisabledException("iPhone support is disabled.")
        if not self._context.is_logged_in:
            raise LoginRequiredException("--login required to access iPhone media info endpoint.")
        if not self._iphone_struct_:
            data = self._context.get_iphone_json(path='api/v1/media/{}/info/'.format(self.mediaid), params={})
            self._iphone_struct_ = data['items'][0]
        return self._iphone_struct_

    def _field(self, *keys) -> Any:
        """Lookups given fields in _node, and if not found in _full_metadata. Raises KeyError if not found anywhere."""
        try:
            d = self._node
            for key in keys:
                d = d[key]
            return d
        except KeyError:
            d = self._full_metadata
            for key in keys:
                d = d[key]
            return d

    @property
    def owner_profile(self) -> 'Profile':
        """:class:`Profile` instance of the Post's owner."""
        if not self._owner_profile:
            if 'username' in self._node['owner']:
                owner_struct = self._node['owner']
            else:
                # Sometimes, the 'owner' structure does not contain the username, only the user's ID.  In that case,
                # this call triggers downloading of the complete Post metadata struct, where the owner username
                # is contained.
                # Note that we cannot use Profile.from_id() here since that would lead us into a recursion.
                owner_struct = self._full_metadata['owner']
            self._owner_profile = Profile(self._context, owner_struct)
        return self._owner_profile

    @property
    def owner_username(self) -> str:
        """The Post's lowercase owner name."""
        return self.owner_profile.username

    @property
    def owner_id(self) -> int:
        """The ID of the Post's owner."""
        # The ID may already be available, e.g. if the post instance was created
        # from an `hashtag.get_posts()` iterator, so no need to make another
        # http request.
        if 'owner' in self._node and 'id' in self._node['owner']:
            return self._node['owner']['id']
        else:
            return self.owner_profile.userid

    @property
    def date_local(self) -> datetime:
        """Timestamp when the post was created (local time zone).

        .. versionchanged:: 4.9
           Return timezone aware datetime object."""
        return datetime.fromtimestamp(self._get_timestamp_date_created()).astimezone()

    @property
    def date_utc(self) -> datetime:
        """Timestamp when the post was created (UTC)."""
        return datetime.utcfromtimestamp(self._get_timestamp_date_created())

    @property
    def date(self) -> datetime:
        """Synonym to :attr:`~Post.date_utc`"""
        return self.date_utc

    @property
    def profile(self) -> str:
        """Synonym to :attr:`~Post.owner_username`"""
        return self.owner_username

    @property
    def url(self) -> str:
        """URL of the picture / video thumbnail of the post"""
        if self.typename == "GraphImage" and self._context.iphone_support and self._context.is_logged_in:
            try:
                orig_url = self._iphone_struct['image_versions2']['candidates'][0]['url']
                url = re.sub(r'([?&])se=\d+&?', r'\1', orig_url).rstrip('&')
                return url
            except (InstaloaderException, KeyError, IndexError) as err:
                self._context.error(f"Unable to fetch high quality image version of {self}: {err}")
        return self._node["display_url"] if "display_url" in self._node else self._node["display_src"]

    @property
    def typename(self) -> str:
        """Type of post, GraphImage, GraphVideo or GraphSidecar"""
        return self._field('__typename')

    @property
    def mediacount(self) -> int:
        """
        The number of media in a sidecar Post, or 1 if the Post it not a sidecar.

        .. versionadded:: 4.6
        """
        if self.typename == 'GraphSidecar':
            edges = self._field('edge_sidecar_to_children', 'edges')
            return len(edges)
        return 1

    def _get_timestamp_date_created(self) -> float:
        """Timestamp when the post was created"""
        return (self._node["date"]
                if "date" in self._node
                else self._node["taken_at_timestamp"])

    def get_is_videos(self) -> List[bool]:
        """
        Return a list containing the ``is_video`` property for each media in the post.

        .. versionadded:: 4.7
        """
        if self.typename == 'GraphSidecar':
            edges = self._field('edge_sidecar_to_children', 'edges')
            return [edge['node']['is_video'] for edge in edges]
        return [self.is_video]

    def get_sidecar_nodes(self, start=0, end=-1) -> Iterator[PostSidecarNode]:
        """
        Sidecar nodes of a Post with typename==GraphSidecar.

        .. versionchanged:: 4.6
           Added parameters *start* and *end* to specify a slice of sidecar media.
        """
        if self.typename == 'GraphSidecar':
            edges = self._field('edge_sidecar_to_children', 'edges')
            if end < 0:
                end = len(edges)-1
            if start < 0:
                start = len(edges)-1
            if any(edge['node']['is_video'] and 'video_url' not in edge['node'] for edge in edges[start:(end+1)]):
                # video_url is only present in full metadata, issue #558.
                edges = self._full_metadata['edge_sidecar_to_children']['edges']
            for idx, edge in enumerate(edges):
                if start <= idx <= end:
                    node = edge['node']
                    is_video = node['is_video']
                    display_url = node['display_url']
                    if not is_video and self._context.iphone_support and self._context.is_logged_in:
                        try:
                            carousel_media = self._iphone_struct['carousel_media']
                            orig_url = carousel_media[idx]['image_versions2']['candidates'][0]['url']
                            display_url = re.sub(r'([?&])se=\d+&?', r'\1', orig_url).rstrip('&')
                        except (InstaloaderException, KeyError, IndexError) as err:
                            self._context.error(f"Unable to fetch high quality image version of {self}: {err}")
                    yield PostSidecarNode(is_video=is_video, display_url=display_url,
                                          video_url=node['video_url'] if is_video else None)

    @property
    def caption(self) -> Optional[str]:
        """Caption."""
        if "edge_media_to_caption" in self._node and self._node["edge_media_to_caption"]["edges"]:
            return _optional_normalize(self._node["edge_media_to_caption"]["edges"][0]["node"]["text"])
        elif "caption" in self._node:
            return _optional_normalize(self._node["caption"])
        return None

    @property
    def caption_hashtags(self) -> List[str]:
        """List of all lowercased hashtags (without preceeding #) that occur in the Post's caption."""
        if not self.caption:
            return []
        return _hashtag_regex.findall(self.caption.lower())

    @property
    def caption_mentions(self) -> List[str]:
        """List of all lowercased profiles that are mentioned in the Post's caption, without preceeding @."""
        if not self.caption:
            return []
        return _mention_regex.findall(self.caption.lower())

    @property
    def pcaption(self) -> str:
        """Printable caption, useful as a format specifier for --filename-pattern.

        .. versionadded:: 4.2.6"""
        def _elliptify(caption):
            pcaption = ' '.join([s.replace('/', '\u2215') for s in caption.splitlines() if s]).strip()
            return (pcaption[:30] + "\u2026") if len(pcaption) > 31 else pcaption
        return _elliptify(self.caption) if self.caption else ''

    @property
    def accessibility_caption(self) -> Optional[str]:
        """Accessibility caption of the post, if available.

        .. versionadded:: 4.9"""
        try:
            return self._field("accessibility_caption")
        except KeyError:
            return None

    @property
    def tagged_users(self) -> List[str]:
        """List of all lowercased users that are tagged in the Post."""
        try:
            return [edge['node']['user']['username'].lower() for edge in self._field('edge_media_to_tagged_user',
                                                                                     'edges')]
        except KeyError:
            return []

    @property
    def is_video(self) -> bool:
        """True if the Post is a video."""
        return self._node['is_video']

    @property
    def video_url(self) -> Optional[str]:
        """URL of the video, or None."""
        if self.is_video:
            version_urls = []
            try:
                version_urls.append(self._field('video_url'))
            except (InstaloaderException, KeyError, IndexError) as err:
                self._context.error(f"Warning: Unable to fetch video from graphql of {self}: {err}")
            if self._context.iphone_support and self._context.is_logged_in:
                try:
                    version_urls.extend(version['url'] for version in self._iphone_struct['video_versions'])
                except (InstaloaderException, KeyError, IndexError) as err:
                    self._context.error(f"Unable to fetch high-quality video version of {self}: {err}")
            version_urls = list(dict.fromkeys(version_urls))
            if len(version_urls) == 0:
                return None
            if len(version_urls) == 1:
                return version_urls[0]
            url_candidates: List[Tuple[int, str]] = []
            for idx, version_url in enumerate(version_urls):
                try:
                    url_candidates.append((
                        int(self._context.head(version_url, allow_redirects=True).headers.get('Content-Length', 0)),
                        version_url
                    ))
                except (InstaloaderException, KeyError, IndexError) as err:
                    self._context.error(f"Video URL candidate {idx+1}/{len(version_urls)} for {self}: {err}")
            if not url_candidates:
                # All candidates fail: Fallback to default URL and handle errors later at the actual download attempt
                return version_urls[0]
            url_candidates.sort()
            return url_candidates[-1][1]
        return None

    @property
    def video_view_count(self) -> Optional[int]:
        """View count of the video, or None.

        .. versionadded:: 4.2.6"""
        if self.is_video:
            return self._field('video_view_count')
        return None

    @property
    def video_duration(self) -> Optional[float]:
        """Duration of the video in seconds, or None.

        .. versionadded:: 4.2.6"""
        if self.is_video:
            return self._field('video_duration')
        return None

    @property
    def viewer_has_liked(self) -> Optional[bool]:
        """Whether the viewer has liked the post, or None if not logged in."""
        if not self._context.is_logged_in:
            return None
        if 'likes' in self._node and 'viewer_has_liked' in self._node['likes']:
            return self._node['likes']['viewer_has_liked']
        return self._field('viewer_has_liked')

    @property
    def likes(self) -> int:
        """Likes count"""
        return self._field('edge_media_preview_like', 'count')

    @property
    def comments(self) -> int:
        """Comment count including answers"""
        # If the count is already present in `self._node`, do not use `self._field` which could trigger fetching the
        # full metadata dict.
        comments = self._node.get('edge_media_to_comment')
        if comments and 'count' in comments:
            return comments['count']
        try:
            return self._field('edge_media_to_parent_comment', 'count')
        except KeyError:
            return self._field('edge_media_to_comment', 'count')

    def _get_comments_via_iphone_endpoint(self) -> Iterable[PostComment]:
        """
        Iterate over all comments of the post via an iPhone endpoint.

        .. versionadded:: 4.10.3
           fallback for :issue:`2125`.
        """
        def _query(min_id=None):
            pagination_params = {"min_id": min_id} if min_id is not None else {}
            return self._context.get_iphone_json(
                f"api/v1/media/{self.mediaid}/comments/",
                {
                    "can_support_threading": "true",
                    "permalink_enabled": "false",
                    **pagination_params,
                },
            )

        def _answers(comment_node):
            def _answer(child_comment):
                return PostCommentAnswer(
                    id=int(child_comment["pk"]),
                    created_at_utc=datetime.utcfromtimestamp(child_comment["created_at"]),
                    text=child_comment["text"],
                    owner=Profile.from_iphone_struct(self._context, child_comment["user"]),
                    likes_count=child_comment["comment_like_count"],
                )

            child_comment_count = comment_node["child_comment_count"]
            if child_comment_count == 0:
                return
            preview_child_comments = comment_node["preview_child_comments"]
            if child_comment_count == len(preview_child_comments):
                yield from (
                    _answer(child_comment) for child_comment in preview_child_comments
                )
                return
            pk = comment_node["pk"]
            answers_json = self._context.get_iphone_json(
                f"api/v1/media/{self.mediaid}/comments/{pk}/child_comments/",
                {"max_id": ""},
            )
            yield from (
                _answer(child_comment) for child_comment in answers_json["child_comments"]
            )

        def _paginated_comments(comments_json):
            for comment_node in comments_json.get("comments", []):
                yield PostComment(
                    id=int(comment_node["pk"]),
                    created_at_utc=datetime.utcfromtimestamp(comment_node["created_at"]),
                    text=comment_node["text"],
                    owner=Profile.from_iphone_struct(self._context, comment_node["user"]),
                    likes_count=comment_node["comment_like_count"],
                    answers=_answers(comment_node),
                )

            next_min_id = comments_json.get("next_min_id")
            if next_min_id:
                yield from _paginated_comments(_query(next_min_id))

        return _paginated_comments(_query())

    def get_comments(self) -> Iterable[PostComment]:
        """Iterate over all comments of the post.

        Each comment is represented by a PostComment NamedTuple with fields text (string), created_at (datetime),
        id (int), owner (:class:`Profile`) and answers (:class:`~typing.Iterator` [:class:`PostCommentAnswer`])
        if available.

        .. versionchanged:: 4.7
           Change return type to ``Iterable``.
        """
        def _postcommentanswer(node):
            return PostCommentAnswer(id=int(node['id']),
                                     created_at_utc=datetime.utcfromtimestamp(node['created_at']),
                                     text=node['text'],
                                     owner=Profile(self._context, node['owner']),
                                     likes_count=node.get('edge_liked_by', {}).get('count', 0))

        def _postcommentanswers(node):
            if 'edge_threaded_comments' not in node:
                return
            answer_count = node['edge_threaded_comments']['count']
            if answer_count == 0:
                # Avoid doing additional requests if there are no comment answers
                return
            answer_edges = node['edge_threaded_comments']['edges']
            if answer_count == len(answer_edges):
                # If the answer's metadata already contains all comments, don't do GraphQL requests to obtain them
                yield from (_postcommentanswer(comment['node']) for comment in answer_edges)
                return
            yield from NodeIterator(
                self._context,
                '51fdd02b67508306ad4484ff574a0b62',
                lambda d: d['data']['comment']['edge_threaded_comments'],
                _postcommentanswer,
                {'comment_id': node['id']},
                'https://www.instagram.com/p/{0}/'.format(self.shortcode),
            )

        def _postcomment(node):
            return PostComment(*_postcommentanswer(node),
                               answers=_postcommentanswers(node))
        if self.comments == 0:
            # Avoid doing additional requests if there are no comments
            return []

        comment_edges = self._field('edge_media_to_comment', 'edges')
        answers_count = sum(edge['node'].get('edge_threaded_comments', {}).get('count', 0) for edge in comment_edges)

        if self.comments == len(comment_edges) + answers_count:
            # If the Post's metadata already contains all parent comments, don't do GraphQL requests to obtain them
            return [_postcomment(comment['node']) for comment in comment_edges]

        if self.comments > NodeIterator.page_length():
            # comments pagination via our graphql query does not work reliably anymore (issue #2125), fallback to an
            # iphone endpoint if needed.
            return self._get_comments_via_iphone_endpoint()

        return NodeIterator(
            self._context,
            '97b41c52301f77ce508f55e66d17620e',
            lambda d: d['data']['shortcode_media']['edge_media_to_parent_comment'],
            _postcomment,
            {'shortcode': self.shortcode},
            'https://www.instagram.com/p/{0}/'.format(self.shortcode),
        )

    def get_likes(self) -> Iterator['Profile']:
        """
        Iterate over all likes of the post. A :class:`Profile` instance of each likee is yielded.

        .. versionchanged:: 4.5.4
           Require being logged in (as required by Instagram).
        """
        if not self._context.is_logged_in:
            raise LoginRequiredException("--login required to access likes of a post.")
        if self.likes == 0:
            # Avoid doing additional requests if there are no comments
            return
        likes_edges = self._field('edge_media_preview_like', 'edges')
        if self.likes == len(likes_edges):
            # If the Post's metadata already contains all likes, don't do GraphQL requests to obtain them
            yield from (Profile(self._context, like['node']) for like in likes_edges)
            return
        yield from NodeIterator(
            self._context,
            '1cb6ec562846122743b61e492c85999f',
            lambda d: d['data']['shortcode_media']['edge_liked_by'],
            lambda n: Profile(self._context, n),
            {'shortcode': self.shortcode},
            'https://www.instagram.com/p/{0}/'.format(self.shortcode),
        )

    @property
    def is_sponsored(self) -> bool:
        """
        Whether Post is a sponsored post, equivalent to non-empty :meth:`Post.sponsor_users`.

        .. versionadded:: 4.4
        """
        try:
            sponsor_edges = self._field('edge_media_to_sponsor_user', 'edges')
        except KeyError:
            return False
        return bool(sponsor_edges)

    @property
    def sponsor_users(self) -> List['Profile']:
        """
        The Post's sponsors.

        .. versionadded:: 4.4
        """
        return ([] if not self.is_sponsored else
                [Profile(self._context, edge['node']['sponsor']) for edge in
                 self._field('edge_media_to_sponsor_user', 'edges')])

    @property
    def location(self) -> Optional[PostLocation]:
        """
        If the Post has a location, returns PostLocation NamedTuple with fields 'id', 'lat' and 'lng' and 'name'.

        .. versionchanged:: 4.2.9
           Require being logged in (as required by Instagram), return None if not logged-in.
        """
        loc = self._field("location")
        if self._location or not loc:
            return self._location
        if not self._context.is_logged_in:
            return None
        location_id = int(loc['id'])
        if any(k not in loc for k in ('name', 'slug', 'has_public_page', 'lat', 'lng')):
            loc.update(self._context.get_json("explore/locations/{0}/".format(location_id),
                                              params={'__a': 1, '__d': 'dis'})['native_location_data']['location_info'])
        self._location = PostLocation(location_id, loc['name'], loc['slug'], loc['has_public_page'],
                                      loc.get('lat'), loc.get('lng'))
        return self._location

    @property
    def is_pinned(self) -> bool:
        """
        .. deprecated: 4.10.3
           This information is not returned by IG anymore

        Used to return True if this Post has been pinned by at least one user, now likely returns always false.

        .. versionadded: 4.9.2"""
        return 'pinned_for_users' in self._node and bool(self._node['pinned_for_users'])


class Profile:
    """
    An Instagram Profile.

    Provides methods for accessing profile properties, as well as :meth:`Profile.get_posts` and for own profile
    :meth:`Profile.get_saved_posts`.

    Get instances with :meth:`Post.owner_profile`, :meth:`StoryItem.owner_profile`, :meth:`Profile.get_followees`,
    :meth:`Profile.get_followers` or::

       L = Instaloader()
       profile = Profile.from_username(L.context, USERNAME)

    Provides :meth:`Profile.get_posts` and for own profile :meth:`Profile.get_saved_posts` to iterate over associated
    :class:`Post` objects::

       for post in profile.get_posts():
           L.download_post(post, target=profile.username)

    :meth:`Profile.get_followees` and :meth:`Profile.get_followers`::

       print("{} follows these profiles:".format(profile.username))
       for followee in profile.get_followees():
           print(followee.username)

    Also, this class implements == and is hashable.
    """
    def __init__(self, context: InstaloaderContext, node: Dict[str, Any]):
        assert 'username' in node
        self._context = context
        self._has_public_story: Optional[bool] = None
        self._node = node
        self._has_full_metadata = False
        self._iphone_struct_ = None
        if 'iphone_struct' in node:
            # if loaded from JSON with load_structure_from_file()
            self._iphone_struct_ = node['iphone_struct']

    @classmethod
    def from_username(cls, context: InstaloaderContext, username: str):
        """Create a Profile instance from a given username, raise exception if it does not exist.

        See also :meth:`Instaloader.check_profile_id`.

        :param context: :attr:`Instaloader.context`
        :param username: Username
        :raises: :class:`ProfileNotExistsException`
        """
        # pylint:disable=protected-access
        profile = cls(context, {'username': username.lower()})
        profile._obtain_metadata()  # to raise ProfileNotExistsException now in case username is invalid
        return profile

    @classmethod
    def from_id(cls, context: InstaloaderContext, profile_id: int):
        """Create a Profile instance from a given userid. If possible, use :meth:`Profile.from_username`
        or constructor directly rather than this method, since it requires more requests.

        :param context: :attr:`Instaloader.context`
        :param profile_id: userid
        :raises: :class:`ProfileNotExistsException`
        """
        if profile_id in context.profile_id_cache:
            return context.profile_id_cache[profile_id]
        data = context.graphql_query('7c16654f22c819fb63d1183034a5162f',
                                     {'user_id': str(profile_id),
                                      'include_chaining': False,
                                      'include_reel': True,
                                      'include_suggested_users': False,
                                      'include_logged_out_extras': False,
                                      'include_highlight_reels': False},
                                     rhx_gis=context.root_rhx_gis)['data']['user']
        if data:
            profile = cls(context, data['reel']['owner'])
        else:
            raise ProfileNotExistsException("No profile found, the user may have blocked you (ID: " +
                                            str(profile_id) + ").")
        context.profile_id_cache[profile_id] = profile
        return profile

    @classmethod
    def from_iphone_struct(cls, context: InstaloaderContext, media: Dict[str, Any]):
        """Create a profile from a given iphone_struct.

        .. versionadded:: 4.9"""
        return cls(context, {
            "id": media["pk"],
            "username": media["username"],
            "is_private": media["is_private"],
            "full_name": media["full_name"],
            "profile_pic_url_hd": media["profile_pic_url"],
            "iphone_struct": media,
        })

    @classmethod
    def own_profile(cls, context: InstaloaderContext):
        """Return own profile if logged-in.

        :param context: :attr:`Instaloader.context`

        .. versionadded:: 4.5.2"""
        if not context.is_logged_in:
            raise LoginRequiredException("--login required to access own profile.")
        return cls(context, context.graphql_query("d6f4427fbe92d846298cf93df0b937d3", {})["data"]["user"])

    def _asdict(self):
        json_node = self._node.copy()
        # remove posts to avoid "Circular reference detected" exception
        json_node.pop('edge_media_collections', None)
        json_node.pop('edge_owner_to_timeline_media', None)
        json_node.pop('edge_saved_media', None)
        json_node.pop('edge_felix_video_timeline', None)
        if self._iphone_struct_:
            json_node['iphone_struct'] = self._iphone_struct_
        return json_node

    def _obtain_metadata(self):
        try:
            if not self._has_full_metadata:
                metadata = self._context.get_iphone_json(f'api/v1/users/web_profile_info/?username={self.username}',
                                                         params={})
                if metadata['data']['user'] is None:
                    raise ProfileNotExistsException('Profile {} does not exist.'.format(self.username))
                self._node = metadata['data']['user']
                self._has_full_metadata = True
        except (QueryReturnedNotFoundException, KeyError) as err:
            top_search_results = TopSearchResults(self._context, self.username)
            similar_profiles = [profile.username for profile in top_search_results.get_profiles()]
            if similar_profiles:
                if self.username in similar_profiles:
                    raise ProfileNotExistsException(
                        f"Profile {self.username} seems to exist, but could not be loaded.") from err
                raise ProfileNotExistsException('Profile {} does not exist.\nThe most similar profile{}: {}.'
                                                .format(self.username,
                                                        's are' if len(similar_profiles) > 1 else ' is',
                                                        ', '.join(similar_profiles[0:5]))) from err
            raise ProfileNotExistsException('Profile {} does not exist.'.format(self.username)) from err

    def _metadata(self, *keys) -> Any:
        try:
            d = self._node
            for key in keys:
                d = d[key]
            return d
        except KeyError:
            self._obtain_metadata()
            d = self._node
            for key in keys:
                d = d[key]
            return d

    @property
    def _iphone_struct(self) -> Dict[str, Any]:
        if not self._context.iphone_support:
            raise IPhoneSupportDisabledException("iPhone support is disabled.")
        if not self._context.is_logged_in:
            raise LoginRequiredException("--login required to access iPhone profile info endpoint.")
        if not self._iphone_struct_:
            data = self._context.get_iphone_json(path='api/v1/users/{}/info/'.format(self.userid), params={})
            self._iphone_struct_ = data['user']
        return self._iphone_struct_

    @property
    def userid(self) -> int:
        """User ID"""
        return int(self._metadata('id'))

    @property
    def username(self) -> str:
        """Profile Name"""
        return self._metadata('username').lower()

    def __repr__(self):
        return '<Profile {} ({})>'.format(self.username, self.userid)

    def __eq__(self, o: object) -> bool:
        if isinstance(o, Profile):
            return self.userid == o.userid
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.userid)

    @property
    def is_private(self) -> bool:
        return self._metadata('is_private')

    @property
    def followed_by_viewer(self) -> bool:
        return self._metadata('followed_by_viewer')

    @property
    def mediacount(self) -> int:
        return self._metadata('edge_owner_to_timeline_media', 'count')

    @property
    def igtvcount(self) -> int:
        return self._metadata('edge_felix_video_timeline', 'count')

    @property
    def followers(self) -> int:
        return self._metadata('edge_followed_by', 'count')

    @property
    def followees(self) -> int:
        return self._metadata('edge_follow', 'count')

    @property
    def external_url(self) -> Optional[str]:
        return self._metadata('external_url')

    @property
    def is_business_account(self) -> bool:
        """.. versionadded:: 4.4"""
        return self._metadata('is_business_account')

    @property
    def business_category_name(self) -> str:
        """.. versionadded:: 4.4"""
        return self._metadata('business_category_name')

    @property
    def biography(self) -> str:
        return normalize("NFC", self._metadata('biography'))

    @property
    def biography_hashtags(self) -> List[str]:
        """
        List of all lowercased hashtags (without preceeding #) that occur in the Profile's biography.

        .. versionadded:: 4.10
        """
        if not self.biography:
            return []
        return _hashtag_regex.findall(self.biography.lower())

    @property
    def biography_mentions(self) -> List[str]:
        """
        List of all lowercased profiles that are mentioned in the Profile's biography, without preceeding @.

        .. versionadded:: 4.10
        """
        if not self.biography:
            return []
        return _mention_regex.findall(self.biography.lower())

    @property
    def blocked_by_viewer(self) -> bool:
        return self._metadata('blocked_by_viewer')

    @property
    def follows_viewer(self) -> bool:
        return self._metadata('follows_viewer')

    @property
    def full_name(self) -> str:
        return self._metadata('full_name')

    @property
    def has_blocked_viewer(self) -> bool:
        return self._metadata('has_blocked_viewer')

    @property
    def has_highlight_reels(self) -> bool:
        """
        .. deprecated:: 4.0.6
           Always returns `True` since :issue:`153`.

        Before broken, this indicated whether the :class:`Profile` had available stories.
        """
        return True

    @property
    def has_public_story(self) -> bool:
        if not self._has_public_story:
            self._obtain_metadata()
            # query rate might be limited:
            data = self._context.graphql_query('9ca88e465c3f866a76f7adee3871bdd8',
                                               {'user_id': self.userid, 'include_chaining': False,
                                                'include_reel': False, 'include_suggested_users': False,
                                                'include_logged_out_extras': True,
                                                'include_highlight_reels': False},
                                               'https://www.instagram.com/{}/'.format(self.username))
            self._has_public_story = data['data']['user']['has_public_story']
        assert self._has_public_story is not None
        return self._has_public_story

    @property
    def has_viewable_story(self) -> bool:
        """
        .. deprecated:: 4.0.6

        Some stories are private. This property determines if the :class:`Profile`
        has at least one story which can be viewed using the associated :class:`InstaloaderContext`,
        i.e. the viewer has privileges to view it.
        """
        return self.has_public_story or self.followed_by_viewer and self.has_highlight_reels

    @property
    def has_requested_viewer(self) -> bool:
        return self._metadata('has_requested_viewer')

    @property
    def is_verified(self) -> bool:
        return self._metadata('is_verified')

    @property
    def requested_by_viewer(self) -> bool:
        return self._metadata('requested_by_viewer')

    @property
    def profile_pic_url(self) -> str:
        """Return URL of profile picture. If logged in, the HD version is returned, otherwise a lower-quality version.

        .. versionadded:: 4.0.3

        .. versionchanged:: 4.2.1
           Require being logged in for HD version (as required by Instagram)."""
        if self._context.iphone_support and self._context.is_logged_in:
            try:
                return self._iphone_struct['hd_profile_pic_url_info']['url']
            except (InstaloaderException, KeyError) as err:
                self._context.error(f"Unable to fetch high quality profile pic: {err}")
                return self._metadata("profile_pic_url_hd")
        else:
            return self._metadata("profile_pic_url_hd")

    @property
    def profile_pic_url_no_iphone(self) -> str:
        """Return URL of lower-quality profile picture.

        .. versionadded:: 4.9.3"""
        return self._metadata("profile_pic_url_hd")

    def get_profile_pic_url(self) -> str:
        """.. deprecated:: 4.0.3

	   Use :attr:`profile_pic_url`."""
        return self.profile_pic_url

    def get_posts(self) -> NodeIterator[Post]:
        """Retrieve all posts from a profile.

        :rtype: NodeIterator[Post]"""
        self._obtain_metadata()
        return NodeIterator(
            self._context,
            '003056d32c2554def87228bc3fd9668a',
            lambda d: d['data']['user']['edge_owner_to_timeline_media'],
            lambda n: Post(self._context, n, self),
            {'id': self.userid},
            'https://www.instagram.com/{0}/'.format(self.username),
            self._metadata('edge_owner_to_timeline_media'),
            Profile._make_is_newest_checker()
        )

    def get_saved_posts(self) -> NodeIterator[Post]:
        """Get Posts that are marked as saved by the user.

        :rtype: NodeIterator[Post]"""

        if self.username != self._context.username:
            raise LoginRequiredException("--login={} required to get that profile's saved posts.".format(self.username))

        return NodeIterator(
            self._context,
            'f883d95537fbcd400f466f63d42bd8a1',
            lambda d: d['data']['user']['edge_saved_media'],
            lambda n: Post(self._context, n),
            {'id': self.userid},
            'https://www.instagram.com/{0}/'.format(self.username),
        )

    def get_tagged_posts(self) -> NodeIterator[Post]:
        """Retrieve all posts where a profile is tagged.

        :rtype: NodeIterator[Post]

        .. versionadded:: 4.0.7"""
        self._obtain_metadata()
        return NodeIterator(
            self._context,
            'e31a871f7301132ceaab56507a66bbb7',
            lambda d: d['data']['user']['edge_user_to_photos_of_you'],
            lambda n: Post(self._context, n, self if int(n['owner']['id']) == self.userid else None),
            {'id': self.userid},
            'https://www.instagram.com/{0}/'.format(self.username),
            is_first=Profile._make_is_newest_checker()
        )

    def get_igtv_posts(self) -> NodeIterator[Post]:
        """Retrieve all IGTV posts.

        :rtype: NodeIterator[Post]

        .. versionadded:: 4.3"""
        self._obtain_metadata()
        return NodeIterator(
            self._context,
            'bc78b344a68ed16dd5d7f264681c4c76',
            lambda d: d['data']['user']['edge_felix_video_timeline'],
            lambda n: Post(self._context, n, self),
            {'id': self.userid},
            'https://www.instagram.com/{0}/channel/'.format(self.username),
            self._metadata('edge_felix_video_timeline'),
            Profile._make_is_newest_checker()
        )

    @staticmethod
    def _make_is_newest_checker() -> Callable[[Post, Optional[Post]], bool]:
        return lambda post, first: first is None or post.date_local > first.date_local

    def get_followed_hashtags(self) -> NodeIterator['Hashtag']:
        """
        Retrieve list of hashtags followed by given profile.
        To use this, one needs to be logged in and private profiles has to be followed.

        :rtype: NodeIterator[Hashtag]

        .. versionadded:: 4.10
        """
        if not self._context.is_logged_in:
            raise LoginRequiredException("--login required to get a profile's followers.")
        self._obtain_metadata()
        return NodeIterator(
            self._context,
            'e6306cc3dbe69d6a82ef8b5f8654c50b',
            lambda d: d["data"]["user"]["edge_following_hashtag"],
            lambda n: Hashtag(self._context, n),
            {'id': str(self.userid)},
            'https://www.instagram.com/{0}/'.format(self.username),
        )

    def get_followers(self) -> NodeIterator['Profile']:
        """
        Retrieve list of followers of given profile.
        To use this, one needs to be logged in and private profiles has to be followed.

        :rtype: NodeIterator[Profile]
        """
        if not self._context.is_logged_in:
            raise LoginRequiredException("--login required to get a profile's followers.")
        self._obtain_metadata()
        return NodeIterator(
            self._context,
            '37479f2b8209594dde7facb0d904896a',
            lambda d: d['data']['user']['edge_followed_by'],
            lambda n: Profile(self._context, n),
            {'id': str(self.userid)},
            'https://www.instagram.com/{0}/'.format(self.username),
        )

    def get_followees(self) -> NodeIterator['Profile']:
        """
        Retrieve list of followees (followings) of given profile.
        To use this, one needs to be logged in and private profiles has to be followed.

        :rtype: NodeIterator[Profile]
        """
        if not self._context.is_logged_in:
            raise LoginRequiredException("--login required to get a profile's followees.")
        self._obtain_metadata()
        return NodeIterator(
            self._context,
            '58712303d941c6855d4e888c5f0cd22f',
            lambda d: d['data']['user']['edge_follow'],
            lambda n: Profile(self._context, n),
            {'id': str(self.userid)},
            'https://www.instagram.com/{0}/'.format(self.username),
        )

    def get_similar_accounts(self) -> Iterator['Profile']:
        """
        Retrieve list of suggested / similar accounts for this profile.
        To use this, one needs to be logged in.

        .. versionadded:: 4.4
        """
        if not self._context.is_logged_in:
            raise LoginRequiredException("--login required to get a profile's similar accounts.")
        self._obtain_metadata()
        yield from (Profile(self._context, edge["node"]) for edge in
                    self._context.graphql_query("ad99dd9d3646cc3c0dda65debcd266a7",
                                                {"user_id": str(self.userid), "include_chaining": True},
                                                "https://www.instagram.com/{0}/"
                                                .format(self.username))["data"]["user"]["edge_chaining"]["edges"])


class StoryItem:
    """
    Structure containing information about a user story item i.e. image or video.

    Created by method :meth:`Story.get_items`. This class implements == and is hashable.

    :param context: :class:`InstaloaderContext` instance used for additional queries if necessary.
    :param node: Dictionary containing the available information of the story item.
    :param owner_profile: :class:`Profile` instance representing the story owner.
    """

    def __init__(self, context: InstaloaderContext, node: Dict[str, Any], owner_profile: Optional[Profile] = None):
        self._context = context
        self._node = node
        self._owner_profile = owner_profile
        self._iphone_struct_ = None
        if 'iphone_struct' in node:
            # if loaded from JSON with load_structure_from_file()
            self._iphone_struct_ = node['iphone_struct']

    def _asdict(self):
        node = self._node
        if self._owner_profile:
            node['owner'] = self._owner_profile._asdict()
        if self._iphone_struct_:
            node['iphone_struct'] = self._iphone_struct_
        return node

    @property
    def mediaid(self) -> int:
        """The mediaid is a decimal representation of the media shortcode."""
        return int(self._node['id'])

    @property
    def shortcode(self) -> str:
        """Convert :attr:`~StoryItem.mediaid` to a shortcode-like string, allowing ``{shortcode}`` to be used with
        :option:`--filename-pattern`."""
        return Post.mediaid_to_shortcode(self.mediaid)

    def __repr__(self):
        return '<StoryItem {}>'.format(self.mediaid)

    def __eq__(self, o: object) -> bool:
        if isinstance(o, StoryItem):
            return self.mediaid == o.mediaid
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.mediaid)

    @classmethod
    def from_mediaid(cls, context: InstaloaderContext, mediaid: int):
        """Create a StoryItem object from a given mediaid.

        .. versionadded:: 4.9
        """
        pic_json = context.graphql_query(
            '2b0673e0dc4580674a88d426fe00ea90',
            {'shortcode': Post.mediaid_to_shortcode(mediaid)}
        )
        shortcode_media = pic_json['data']['shortcode_media']
        if shortcode_media is None:
            raise BadResponseException("Fetching StoryItem metadata failed.")
        return cls(context, shortcode_media)

    @property
    def _iphone_struct(self) -> Dict[str, Any]:
        if not self._context.iphone_support:
            raise IPhoneSupportDisabledException("iPhone support is disabled.")
        if not self._context.is_logged_in:
            raise LoginRequiredException("--login required to access iPhone media info endpoint.")
        if not self._iphone_struct_:
            data = self._context.get_iphone_json(
                path='api/v1/feed/reels_media/?reel_ids={}'.format(self.owner_id), params={}
            )
            self._iphone_struct_ = {}
            for item in data['reels'][str(self.owner_id)]['items']:
                if item['pk'] == self.mediaid:
                    self._iphone_struct_ = item
                    break
        return self._iphone_struct_

    @property
    def owner_profile(self) -> Profile:
        """:class:`Profile` instance of the story item's owner."""
        if not self._owner_profile:
            self._owner_profile = Profile.from_id(self._context, self._node['owner']['id'])
        assert self._owner_profile is not None
        return self._owner_profile

    @property
    def owner_username(self) -> str:
        """The StoryItem owner's lowercase name."""
        return self.owner_profile.username

    @property
    def owner_id(self) -> int:
        """The ID of the StoryItem owner."""
        return self.owner_profile.userid

    @property
    def date_local(self) -> datetime:
        """Timestamp when the StoryItem was created (local time zone).

        .. versionchanged:: 4.9
           Return timezone aware datetime object."""
        return datetime.fromtimestamp(self._node['taken_at_timestamp']).astimezone()

    @property
    def date_utc(self) -> datetime:
        """Timestamp when the StoryItem was created (UTC)."""
        return datetime.utcfromtimestamp(self._node['taken_at_timestamp'])

    @property
    def date(self) -> datetime:
        """Synonym to :attr:`~StoryItem.date_utc`"""
        return self.date_utc

    @property
    def profile(self) -> str:
        """Synonym to :attr:`~StoryItem.owner_username`"""
        return self.owner_username

    @property
    def expiring_local(self) -> datetime:
        """Timestamp when the StoryItem will get unavailable (local time zone)."""
        return datetime.fromtimestamp(self._node['expiring_at_timestamp'])

    @property
    def expiring_utc(self) -> datetime:
        """Timestamp when the StoryItem will get unavailable (UTC)."""
        return datetime.utcfromtimestamp(self._node['expiring_at_timestamp'])

    @property
    def url(self) -> str:
        """URL of the picture / video thumbnail of the StoryItem"""
        if self.typename in ["GraphStoryImage", "StoryImage"] and \
                self._context.iphone_support and self._context.is_logged_in:
            try:
                orig_url = self._iphone_struct['image_versions2']['candidates'][0]['url']
                url = re.sub(r'([?&])se=\d+&?', r'\1', orig_url).rstrip('&')
                return url
            except (InstaloaderException, KeyError, IndexError) as err:
                self._context.error(f"Unable to fetch high quality image version of {self}: {err}")
        return self._node['display_resources'][-1]['src']

    @property
    def typename(self) -> str:
        """Type of post, GraphStoryImage or GraphStoryVideo"""
        return self._node['__typename']

    @property
    def caption(self) -> Optional[str]:
        """
        Caption.

        .. versionadded:: 4.10
        """
        if "edge_media_to_caption" in self._node and self._node["edge_media_to_caption"]["edges"]:
            return _optional_normalize(self._node["edge_media_to_caption"]["edges"][0]["node"]["text"])
        elif "caption" in self._node:
            return _optional_normalize(self._node["caption"])
        return None

    @property
    def caption_hashtags(self) -> List[str]:
        """
        List of all lowercased hashtags (without preceeding #) that occur in the StoryItem's caption.

        .. versionadded:: 4.10
        """
        if not self.caption:
            return []
        return _hashtag_regex.findall(self.caption.lower())

    @property
    def caption_mentions(self) -> List[str]:
        """
        List of all lowercased profiles that are mentioned in the StoryItem's caption, without preceeding @.

        .. versionadded:: 4.10
        """
        if not self.caption:
            return []
        return _mention_regex.findall(self.caption.lower())

    @property
    def pcaption(self) -> str:
        """
        Printable caption, useful as a format specifier for --filename-pattern.

        .. versionadded:: 4.10
        """
        def _elliptify(caption):
            pcaption = ' '.join([s.replace('/', '\u2215') for s in caption.splitlines() if s]).strip()
            return (pcaption[:30] + "\u2026") if len(pcaption) > 31 else pcaption
        return _elliptify(self.caption) if self.caption else ''

    @property
    def is_video(self) -> bool:
        """True if the StoryItem is a video."""
        return self._node['is_video']

    @property
    def video_url(self) -> Optional[str]:
        """URL of the video, or None."""
        if self.is_video:
            version_urls = []
            try:
                version_urls.append(self._node['video_resources'][-1]['src'])
            except (InstaloaderException, KeyError, IndexError) as err:
                self._context.error(f"Warning: Unable to fetch video from graphql of {self}: {err}")
            if self._context.iphone_support and self._context.is_logged_in:
                try:
                    version_urls.extend(version['url'] for version in self._iphone_struct['video_versions'])
                except (InstaloaderException, KeyError, IndexError) as err:
                    self._context.error(f"Unable to fetch high-quality video version of {self}: {err}")
            version_urls = list(dict.fromkeys(version_urls))
            if len(version_urls) == 0:
                return None
            if len(version_urls) == 1:
                return version_urls[0]
            url_candidates: List[Tuple[int, str]] = []
            for idx, version_url in enumerate(version_urls):
                try:
                    url_candidates.append((
                        int(self._context.head(version_url, allow_redirects=True).headers.get('Content-Length', 0)),
                        version_url
                    ))
                except (InstaloaderException, KeyError, IndexError) as err:
                    self._context.error(f"Video URL candidate {idx+1}/{len(version_urls)} for {self}: {err}")
            if not url_candidates:
                # All candidates fail: Fallback to default URL and handle errors later at the actual download attempt
                return version_urls[0]
            url_candidates.sort()
            return url_candidates[-1][1]
        return None


class Story:
    """
    Structure representing a user story with its associated items.

    Provides methods for accessing story properties, as well as :meth:`Story.get_items` to request associated
    :class:`StoryItem` nodes. Stories are returned by :meth:`Instaloader.get_stories`.

    With a logged-in :class:`Instaloader` instance `L`, you may download all your visible user stories with::

       for story in L.get_stories():
           # story is a Story object
           for item in story.get_items():
               # item is a StoryItem object
               L.download_storyitem(item, ':stories')

    This class implements == and is hashable.

    :param context: :class:`InstaloaderContext` instance used for additional queries if necessary.
    :param node: Dictionary containing the available information of the story as returned by Instagram.
    """

    def __init__(self, context: InstaloaderContext, node: Dict[str, Any]):
        self._context = context
        self._node = node
        self._unique_id: Optional[str] = None
        self._owner_profile: Optional[Profile] = None
        self._iphone_struct_: Optional[Dict[str, Any]] = None

    def __repr__(self):
        return '<Story by {} changed {:%Y-%m-%d_%H-%M-%S_UTC}>'.format(self.owner_username, self.latest_media_utc)

    def __eq__(self, o: object) -> bool:
        if isinstance(o, Story):
            return self.unique_id == o.unique_id
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.unique_id)

    @property
    def unique_id(self) -> Union[str, int]:
        """
        This ID only equals amongst :class:`Story` instances which have the same owner and the same set of
        :class:`StoryItem`. For all other :class:`Story` instances this ID is different.
        """
        if not self._unique_id:
            id_list = [item.mediaid for item in self.get_items()]
            id_list.sort()
            self._unique_id = str().join([str(self.owner_id)] + list(map(str, id_list)))
        return self._unique_id

    @property
    def last_seen_local(self) -> Optional[datetime]:
        """Timestamp of the most recent StoryItem that has been watched or None (local time zone)."""
        if self._node['seen']:
            return datetime.fromtimestamp(self._node['seen'])
        return None

    @property
    def last_seen_utc(self) -> Optional[datetime]:
        """Timestamp of the most recent StoryItem that has been watched or None (UTC)."""
        if self._node['seen']:
            return datetime.utcfromtimestamp(self._node['seen'])
        return None

    @property
    def latest_media_local(self) -> datetime:
        """Timestamp when the last item of the story was created (local time zone)."""
        return datetime.fromtimestamp(self._node['latest_reel_media'])

    @property
    def latest_media_utc(self) -> datetime:
        """Timestamp when the last item of the story was created (UTC)."""
        return datetime.utcfromtimestamp(self._node['latest_reel_media'])

    @property
    def itemcount(self) -> int:
        """Count of items associated with the :class:`Story` instance."""
        return len(self._node['items'])

    @property
    def owner_profile(self) -> Profile:
        """:class:`Profile` instance of the story owner."""
        if not self._owner_profile:
            self._owner_profile = Profile(self._context, self._node['user'])
        return self._owner_profile

    @property
    def owner_username(self) -> str:
        """The story owner's lowercase username."""
        return self.owner_profile.username

    @property
    def owner_id(self) -> int:
        """The story owner's ID."""
        return self.owner_profile.userid

    def _fetch_iphone_struct(self) -> None:
        if self._context.iphone_support and self._context.is_logged_in and not self._iphone_struct_:
            data = self._context.get_iphone_json(
                path='api/v1/feed/reels_media/?reel_ids={}'.format(self.owner_id), params={}
            )
            self._iphone_struct_ = data['reels'][str(self.owner_id)]

    def get_items(self) -> Iterator[StoryItem]:
        """Retrieve all items from a story."""
        self._fetch_iphone_struct()
        for item in reversed(self._node['items']):
            if self._iphone_struct_ is not None:
                for iphone_struct_item in self._iphone_struct_['items']:
                    if iphone_struct_item['pk'] == int(item['id']):
                        item['iphone_struct'] = iphone_struct_item
                        break
            yield StoryItem(self._context, item, self.owner_profile)


class Highlight(Story):
    """
    Structure representing a user's highlight with its associated story items.

    Provides methods for accessing highlight properties, as well as :meth:`Highlight.get_items` to request associated
    :class:`StoryItem` nodes. Highlights are returned by :meth:`Instaloader.get_highlights`.

    With a logged-in :class:`Instaloader` instance `L`, you may download all highlights of a :class:`Profile` instance
    USER with::

       for highlight in L.get_highlights(USER):
           # highlight is a Highlight object
           for item in highlight.get_items():
               # item is a StoryItem object
               L.download_storyitem(item, '{}/{}'.format(highlight.owner_username, highlight.title))

    This class implements == and is hashable.

    :param context: :class:`InstaloaderContext` instance used for additional queries if necessary.
    :param node: Dictionary containing the available information of the highlight as returned by Instagram.
    :param owner: :class:`Profile` instance representing the owner profile of the highlight.
    """

    def __init__(self, context: InstaloaderContext, node: Dict[str, Any], owner: Optional[Profile] = None):
        super().__init__(context, node)
        self._owner_profile = owner
        self._items: Optional[List[Dict[str, Any]]] = None
        self._iphone_struct_: Optional[Dict[str, Any]] = None

    def __repr__(self):
        return '<Highlight by {}: {}>'.format(self.owner_username, self.title)

    @property
    def unique_id(self) -> int:
        """A unique ID identifying this set of highlights."""
        return int(self._node['id'])

    @property
    def owner_profile(self) -> Profile:
        """:class:`Profile` instance of the highlights' owner."""
        if not self._owner_profile:
            self._owner_profile = Profile(self._context, self._node['owner'])
        return self._owner_profile

    @property
    def title(self) -> str:
        """The title of these highlights."""
        return self._node['title']

    @property
    def cover_url(self) -> str:
        """URL of the highlights' cover."""
        return self._node['cover_media']['thumbnail_src']

    @property
    def cover_cropped_url(self) -> str:
        """URL of the cropped version of the cover."""
        return self._node['cover_media_cropped_thumbnail']['url']

    def _fetch_items(self):
        if not self._items:
            self._items = self._context.graphql_query("45246d3fe16ccc6577e0bd297a5db1ab",
                                                      {"reel_ids": [], "tag_names": [], "location_ids": [],
                                                       "highlight_reel_ids": [str(self.unique_id)],
                                                       "precomposed_overlay": False})['data']['reels_media'][0]['items']

    def _fetch_iphone_struct(self) -> None:
        if self._context.iphone_support and self._context.is_logged_in and not self._iphone_struct_:
            data = self._context.get_iphone_json(
                path='api/v1/feed/reels_media/?reel_ids=highlight:{}'.format(self.unique_id), params={}
            )
            self._iphone_struct_ = data['reels']['highlight:{}'.format(self.unique_id)]

    @property
    def itemcount(self) -> int:
        """Count of items associated with the :class:`Highlight` instance."""
        self._fetch_items()
        assert self._items is not None
        return len(self._items)

    def get_items(self) -> Iterator[StoryItem]:
        """Retrieve all associated highlight items."""
        self._fetch_items()
        self._fetch_iphone_struct()
        assert self._items is not None
        for item in self._items:
            if self._iphone_struct_ is not None:
                for iphone_struct_item in self._iphone_struct_['items']:
                    if iphone_struct_item['pk'] == int(item['id']):
                        item['iphone_struct'] = iphone_struct_item
                        break
            yield StoryItem(self._context, item, self.owner_profile)


class Hashtag:
    """
    An Hashtag.

    Analogous to :class:`Profile`, get an instance with::

       L = Instaloader()
       hashtag = Hashtag.from_name(L.context, HASHTAG)

    To then download the Hashtag's Posts, do::

       for post in hashtag.get_posts():
          L.download_post(post, target="#"+hashtag.name)

    Also, this class implements == and is hashable.

    .. versionchanged:: 4.9
       Removed ``get_related_tags()`` and ``is_top_media_only`` as these features were removed from Instagram.
    """
    def __init__(self, context: InstaloaderContext, node: Dict[str, Any]):
        assert "name" in node
        self._context = context
        self._node = node
        self._has_full_metadata = False

    @classmethod
    def from_name(cls, context: InstaloaderContext, name: str):
        """
        Create a Hashtag instance from a given hashtag name, without preceeding '#'. Raises an Exception if there is no
        hashtag with the given name.

        :param context: :attr:`Instaloader.context`
        :param name: Hashtag, without preceeding '#'
        :raises: :class:`QueryReturnedNotFoundException`
        """
        # pylint:disable=protected-access
        hashtag = cls(context, {'name': name.lower()})
        hashtag._obtain_metadata()
        return hashtag

    @property
    def name(self):
        """Hashtag name lowercased, without preceeding '#'"""
        return self._node["name"].lower()

    def _query(self, params):
        json_response = self._context.get_json("explore/tags/{0}/".format(self.name), params)
        return json_response["graphql"]["hashtag"] if "graphql" in json_response else json_response["data"]

    def _obtain_metadata(self):
        if not self._has_full_metadata:
            self._node = self._query({"__a": 1, "__d": "dis"})
            self._has_full_metadata = True

    def _asdict(self):
        json_node = self._node.copy()
        # remove posts
        json_node.pop("edge_hashtag_to_top_posts", None)
        json_node.pop("top", None)
        json_node.pop("edge_hashtag_to_media", None)
        json_node.pop("recent", None)
        return json_node

    def __repr__(self):
        return "<Hashtag #{}>".format(self.name)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Hashtag):
            return self.name == other.name
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.name)

    def _metadata(self, *keys) -> Any:
        try:
            d = self._node
            for key in keys:
                d = d[key]
            return d
        except KeyError:
            self._obtain_metadata()
            d = self._node
            for key in keys:
                d = d[key]
            return d

    @property
    def hashtagid(self) -> int:
        return int(self._metadata("id"))

    @property
    def profile_pic_url(self) -> str:
        return self._metadata("profile_pic_url")

    @property
    def description(self) -> Optional[str]:
        return self._metadata("description")

    @property
    def allow_following(self) -> bool:
        return bool(self._metadata("allow_following"))

    @property
    def is_following(self) -> bool:
        try:
            return self._metadata("is_following")
        except KeyError:
            return bool(self._metadata("following"))

    def get_top_posts(self) -> Iterator[Post]:
        """Yields the top posts of the hashtag."""
        try:
            yield from (Post(self._context, edge["node"])
                        for edge in self._metadata("edge_hashtag_to_top_posts", "edges"))
        except KeyError:
            yield from SectionIterator(
                self._context,
                lambda d: d["data"]["top"],
                lambda m: Post.from_iphone_struct(self._context, m),
                f"explore/tags/{self.name}/",
                self._metadata("top"),
            )

    @property
    def mediacount(self) -> int:
        """
        The count of all media associated with this hashtag.

        The number of posts with a certain hashtag may differ from the number of posts that can actually be accessed, as
        the hashtag count might include private posts
        """
        try:
            return self._metadata("edge_hashtag_to_media", "count")
        except KeyError:
            return self._metadata("media_count")

    def get_posts(self) -> Iterator[Post]:
        """Yields the recent posts associated with this hashtag.

        .. deprecated:: 4.9
           Use :meth:`Hashtag.get_posts_resumable` as this method may return incorrect results (:issue:`1457`)"""
        try:
            self._metadata("edge_hashtag_to_media", "edges")
            self._metadata("edge_hashtag_to_media", "page_info")
            conn = self._metadata("edge_hashtag_to_media")
            yield from (Post(self._context, edge["node"]) for edge in conn["edges"])
            while conn["page_info"]["has_next_page"]:
                data = self._query({'__a': 1, 'max_id': conn["page_info"]["end_cursor"]})
                conn = data["edge_hashtag_to_media"]
                yield from (Post(self._context, edge["node"]) for edge in conn["edges"])
        except KeyError:
            yield from SectionIterator(
                self._context,
                lambda d: d["data"]["recent"],
                lambda m: Post.from_iphone_struct(self._context, m),
                f"explore/tags/{self.name}/",
                self._metadata("recent"),
            )

    def get_all_posts(self) -> Iterator[Post]:
        """Yields all posts, i.e. all most recent posts and the top posts, in almost-chronological order."""
        sorted_top_posts = iter(sorted(islice(self.get_top_posts(), 9), key=lambda p: p.date_utc, reverse=True))
        other_posts = self.get_posts_resumable()
        next_top = next(sorted_top_posts, None)
        next_other = next(other_posts, None)
        while next_top is not None or next_other is not None:
            if next_other is None:
                assert next_top is not None
                yield next_top
                yield from sorted_top_posts
                break
            if next_top is None:
                assert next_other is not None
                yield next_other
                yield from other_posts
                break
            if next_top == next_other:
                yield next_top
                next_top = next(sorted_top_posts, None)
                next_other = next(other_posts, None)
                continue
            if next_top.date_utc > next_other.date_utc:
                yield next_top
                next_top = next(sorted_top_posts, None)
            else:
                yield next_other
                next_other = next(other_posts, None)

    def get_posts_resumable(self) -> NodeIterator[Post]:
        """Get the recent posts of the hashtag in a resumable fashion.

        :rtype: NodeIterator[Post]

        .. versionadded:: 4.9"""
        return NodeIterator(
            self._context, "9b498c08113f1e09617a1703c22b2f32",
            lambda d: d['data']['hashtag']['edge_hashtag_to_media'],
            lambda n: Post(self._context, n),
            {'tag_name': self.name},
            f"https://www.instagram.com/explore/tags/{self.name}/"
        )


class TopSearchResults:
    """
    An invocation of this class triggers a search on Instagram for the provided search string.

    Provides methods to access the search results as profiles (:class:`Profile`), locations (:class:`PostLocation`) and
    hashtags.

    :param context: :attr:`Instaloader.context` used to send the query for the search.
    :param searchstring: String to search for with Instagram's "top search".
    """

    def __init__(self, context: InstaloaderContext, searchstring: str):
        self._context = context
        self._searchstring = searchstring
        # The `__a` param is only needed to prevent `get_json()` from searching for 'window._sharedData'.
        self._node = context.get_json('web/search/topsearch/',
                                      params={'context': 'blended',
                                              'query': searchstring,
                                              'include_reel': False,
                                              '__a': 1})

    def get_profiles(self) -> Iterator[Profile]:
        """
        Provides the :class:`Profile` instances from the search result.
        """
        for user in self._node.get('users', []):
            user_node = user['user']
            if 'pk' in user_node:
                user_node['id'] = user_node['pk']
            yield Profile(self._context, user_node)

    def get_prefixed_usernames(self) -> Iterator[str]:
        """
        Provides all profile names from the search result that start with the search string.
        """
        for user in self._node.get('users', []):
            username = user.get('user', {}).get('username', '')
            if username.startswith(self._searchstring):
                yield username

    def get_locations(self) -> Iterator[PostLocation]:
        """
        Provides instances of :class:`PostLocation` from the search result.
        """
        for location in self._node.get('places', []):
            place = location.get('place', {})
            slug = place.get('slug')
            loc = place.get('location', {})
            yield PostLocation(int(loc['pk']), loc['name'], slug, None, loc.get('lat'), loc.get('lng'))

    def get_hashtag_strings(self) -> Iterator[str]:
        """
        Provides the hashtags from the search result as strings.
        """
        for hashtag in self._node.get('hashtags', []):
            name = hashtag.get('hashtag', {}).get('name')
            if name:
                yield name

    def get_hashtags(self) -> Iterator[Hashtag]:
        """
        Provides the hashtags from the search result.

        .. versionadded:: 4.4
        """
        for hashtag in self._node.get('hashtags', []):
            node = hashtag.get('hashtag', {})
            if 'name' in node:
                yield Hashtag(self._context, node)

    @property
    def searchstring(self) -> str:
        """
        The string that was searched for on Instagram to produce this :class:`TopSearchResults` instance.
        """
        return self._searchstring


class TitlePic:
    def __init__(self, profile: Optional[Profile], target: Union[str, Path], typename: str,
                 filename: str, date_utc: Optional[datetime]):
        self._profile = profile
        self._target = target
        self._typename = typename
        self._filename = filename
        self._date_utc = date_utc

    @property
    def profile(self) -> Union[str, Path]:
        return self._profile.username.lower() if self._profile is not None else self._target

    @property
    def owner_username(self) -> Union[str, Path]:
        return self.profile

    @property
    def owner_id(self) -> Union[str, Path]:
        return str(self._profile.userid) if self._profile is not None else self._target

    @property
    def target(self) -> Union[str, Path]:
        return self._target

    @property
    def typename(self) -> str:
        return self._typename

    @property
    def filename(self) -> str:
        return self._filename

    @property
    def date_utc(self) -> Optional[datetime]:
        return self._date_utc

    @property
    def date(self) -> Optional[datetime]:
        return self.date_utc

    @property
    def date_local(self) -> Optional[datetime]:
        return self._date_utc.astimezone() if self._date_utc is not None else None


JsonExportable = Union[Post, Profile, StoryItem, Hashtag, FrozenNodeIterator]


def get_json_structure(structure: JsonExportable) -> dict:
    """Returns Instaloader JSON structure for a :class:`Post`, :class:`Profile`, :class:`StoryItem`, :class:`Hashtag`
     or :class:`FrozenNodeIterator` so that it can be loaded by :func:`load_structure`.

    :param structure: :class:`Post`, :class:`Profile`, :class:`StoryItem` or :class:`Hashtag`

    .. versionadded:: 4.8
    """
    return {
        'node': structure._asdict(),
        'instaloader': {'version': __version__, 'node_type': structure.__class__.__name__}
    }


def save_structure_to_file(structure: JsonExportable, filename: str) -> None:
    """Saves a :class:`Post`, :class:`Profile`, :class:`StoryItem`, :class:`Hashtag` or :class:`FrozenNodeIterator` to a
    '.json' or '.json.xz' file such that it can later be loaded by :func:`load_structure_from_file`.

    If the specified filename ends in '.xz', the file will be LZMA compressed. Otherwise, a pretty-printed JSON file
    will be created.

    :param structure: :class:`Post`, :class:`Profile`, :class:`StoryItem` or :class:`Hashtag`
    :param filename: Filename, ends in '.json' or '.json.xz'
    """
    json_structure = get_json_structure(structure)
    compress = filename.endswith('.xz')
    if compress:
        with lzma.open(filename, 'wt', check=lzma.CHECK_NONE) as fp:
            json.dump(json_structure, fp=fp, separators=(',', ':'))
    else:
        with open(filename, 'wt') as fp:
            json.dump(json_structure, fp=fp, indent=4, sort_keys=True)


def load_structure(context: InstaloaderContext, json_structure: dict) -> JsonExportable:
    """Loads a :class:`Post`, :class:`Profile`, :class:`StoryItem`, :class:`Hashtag` or :class:`FrozenNodeIterator` from
    a json structure.

    :param context: :attr:`Instaloader.context` linked to the new object, used for additional queries if neccessary.
    :param json_structure: Instaloader JSON structure

    .. versionadded:: 4.8
    """
    if 'node' in json_structure and 'instaloader' in json_structure and \
            'node_type' in json_structure['instaloader']:
        node_type = json_structure['instaloader']['node_type']
        if node_type == "Post":
            return Post(context, json_structure['node'])
        elif node_type == "Profile":
            return Profile(context, json_structure['node'])
        elif node_type == "StoryItem":
            return StoryItem(context, json_structure['node'])
        elif node_type == "Hashtag":
            return Hashtag(context, json_structure['node'])
        elif node_type == "FrozenNodeIterator":
            if not 'first_node' in json_structure['node']:
                json_structure['node']['first_node'] = None
            return FrozenNodeIterator(**json_structure['node'])
    elif 'shortcode' in json_structure:
        # Post JSON created with Instaloader v3
        return Post.from_shortcode(context, json_structure['shortcode'])
    raise InvalidArgumentException("Passed json structure is not an Instaloader JSON")


def load_structure_from_file(context: InstaloaderContext, filename: str) -> JsonExportable:
    """Loads a :class:`Post`, :class:`Profile`, :class:`StoryItem`, :class:`Hashtag` or :class:`FrozenNodeIterator` from
    a '.json' or '.json.xz' file that has been saved by :func:`save_structure_to_file`.

    :param context: :attr:`Instaloader.context` linked to the new object, used for additional queries if neccessary.
    :param filename: Filename, ends in '.json' or '.json.xz'
    """
    compressed = filename.endswith('.xz')
    if compressed:
        fp = lzma.open(filename, 'rt')
    else:
        # pylint:disable=consider-using-with
        fp = open(filename, 'rt')
    json_structure = json.load(fp)
    fp.close()
    return load_structure(context, json_structure)
