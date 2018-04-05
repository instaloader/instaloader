import re
from base64 import b64decode, b64encode
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional

from .exceptions import *
from .instaloadercontext import GRAPHQL_PAGE_LENGTH, InstaloaderContext


def shortcode_to_mediaid(code: str) -> int:
    if len(code) > 11:
        raise InvalidArgumentException("Wrong shortcode \"{0}\", unable to convert to mediaid.".format(code))
    code = 'A' * (12 - len(code)) + code
    return int.from_bytes(b64decode(code.encode(), b'-_'), 'big')


def mediaid_to_shortcode(mediaid: int) -> str:
    if mediaid.bit_length() > 64:
        raise InvalidArgumentException("Wrong mediaid {0}, unable to convert to shortcode".format(str(mediaid)))
    return b64encode(mediaid.to_bytes(9, 'big'), b'-_').decode().replace('A', ' ').lstrip().replace(' ', 'A')


class Post:
    """
    Structure containing information about an Instagram post.

    Created by methods :meth:`Profile.get_posts`, :meth:`Instaloader.get_hashtag_posts`,
    :meth:`Instaloader.get_feed_posts` and :meth:`Profile.get_saved_posts`.
    This class unifies access to the properties associated with a post. It implements == and is
    hashable.

    The properties defined here are accessible by the filter expressions specified with the :option:`--only-if`
    parameter and exported into JSON files with :option:`--metadata-json`.
    """

    LOGIN_REQUIRING_PROPERTIES = ["viewer_has_liked"]

    def __init__(self, context: InstaloaderContext, node: Dict[str, Any],
                 owner_profile: Optional['Profile'] = None):
        """Create a Post instance from a node structure as returned by Instagram.

        :param context: :class:`InstaloaderContext` instance used for additional queries if neccessary.
        :param node: Node structure, as returned by Instagram.
        :param owner_profile: The Profile of the owner, if already known at creation.
        """
        self._context = context
        self._node = node
        self._owner_profile = owner_profile
        self._full_metadata_dict = None

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
        return cls.from_shortcode(context, mediaid_to_shortcode(mediaid))

    @property
    def shortcode(self) -> str:
        """Media shortcode. URL of the post is instagram.com/p/<shortcode>/."""
        return self._node['shortcode'] if 'shortcode' in self._node else self._node['code']

    @property
    def mediaid(self) -> int:
        """The mediaid is a decimal representation of the media shortcode."""
        return int(self._node['id'])

    def __repr__(self):
        return '<Post {}>'.format(self.shortcode)

    def __eq__(self, o: object) -> bool:
        if isinstance(o, Post):
            return self.shortcode == o.shortcode
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.shortcode)

    @property
    def _full_metadata(self) -> Dict[str, Any]:
        if not self._full_metadata_dict:
            pic_json = self._context.get_json("p/{0}/".format(self.shortcode), params={'__a': 1})
            if "graphql" in pic_json:
                self._full_metadata_dict = pic_json["graphql"]["shortcode_media"]
            else:
                self._full_metadata_dict = pic_json["media"]
        return self._full_metadata_dict

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
    def owner_username(self) -> str:
        """The Post's lowercase owner name, or 'UNKNOWN'."""
        try:
            if self._owner_profile:
                return self._owner_profile.username.lower()
            return self._field('owner', 'username').lower()
        except (InstaloaderException, KeyError, TypeError) as err:
            if self._context.raise_all_errors:
                raise err
            self._context.error("Get owner name of {}: {} -- using \'UNKNOWN\'.".format(self, err))
            return 'UNKNOWN'

    @property
    def owner_id(self) -> int:
        """The ID of the Post's owner."""
        if self._owner_profile:
            return self._owner_profile.userid
        return int(self._field('owner', 'id'))

    @property
    def date_local(self) -> datetime:
        """Timestamp when the post was created (local time zone)."""
        return datetime.fromtimestamp(self._node["date"] if "date" in self._node else self._node["taken_at_timestamp"])

    @property
    def date_utc(self) -> datetime:
        """Timestamp when the post was created (UTC)."""
        return datetime.utcfromtimestamp(self._node["date"] if "date" in self._node else self._node["taken_at_timestamp"])

    @property
    def url(self) -> str:
        """URL of the picture / video thumbnail of the post"""
        return self._node["display_url"] if "display_url" in self._node else self._node["display_src"]

    @property
    def typename(self) -> str:
        """Type of post, GraphImage, GraphVideo or GraphSidecar"""
        if '__typename' in self._node:
            return self._node['__typename']
        # if __typename is not in node, it is an old image or video
        return 'GraphImage'

    def get_sidecar_edges(self) -> List[Dict[str, Any]]:
        return self._field('edge_sidecar_to_children', 'edges')

    @property
    def caption(self) -> Optional[str]:
        """Caption."""
        if "edge_media_to_caption" in self._node and self._node["edge_media_to_caption"]["edges"]:
            return self._node["edge_media_to_caption"]["edges"][0]["node"]["text"]
        elif "caption" in self._node:
            return self._node["caption"]

    @property
    def caption_hashtags(self) -> List[str]:
        """List of all lowercased hashtags (without preceeding #) that occur in the Post's caption."""
        if not self.caption:
            return []
        # This regular expression is from jStassen, adjusted to use Python's \w to support Unicode
        # http://blog.jstassen.com/2016/03/code-regex-for-instagram-username-and-hashtags/
        hashtag_regex = re.compile(r"(?:#)(\w(?:(?:\w|(?:\.(?!\.))){0,28}(?:\w))?)")
        return re.findall(hashtag_regex, self.caption.lower())

    @property
    def caption_mentions(self) -> List[str]:
        """List of all lowercased profiles that are mentioned in the Post's caption, without preceeding @."""
        if not self.caption:
            return []
        # This regular expression is from jStassen, adjusted to use Python's \w to support Unicode
        # http://blog.jstassen.com/2016/03/code-regex-for-instagram-username-and-hashtags/
        mention_regex = re.compile(r"(?:@)(\w(?:(?:\w|(?:\.(?!\.))){0,28}(?:\w))?)")
        return re.findall(mention_regex, self.caption.lower())

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
            return self._field('video_url')

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
        """Comment count"""
        return self._field('edge_media_to_comment', 'count')

    def get_comments(self) -> Iterator[Dict[str, Any]]:
        """Iterate over all comments of the post.

        Each comment is represented by a dictionary having the keys text, created_at, id and owner, which is a
        dictionary with keys username, profile_pic_url and id.
        """
        if self.comments == 0:
            # Avoid doing additional requests if there are no comments
            return
        comment_edges = self._field('edge_media_to_comment', 'edges')
        if self.comments == len(comment_edges):
            # If the Post's metadata already contains all comments, don't do GraphQL requests to obtain them
            yield from (comment['node'] for comment in comment_edges)
        yield from self._context.graphql_node_list("33ba35852cb50da46f5b5e889df7d159",
                                                   {'shortcode': self.shortcode},
                                                   'https://www.instagram.com/p/' + self.shortcode + '/',
                                                   lambda d: d['data']['shortcode_media']['edge_media_to_comment'])

    def get_likes(self) -> Iterator[Dict[str, Any]]:
        """Iterate over all likes of the post.

        Each like is represented by a dictionary having the keys username, followed_by_viewer, id, is_verified,
        requested_by_viewer, followed_by_viewer, profile_pic_url.
        """
        if self.likes == 0:
            # Avoid doing additional requests if there are no comments
            return
        likes_edges = self._field('edge_media_preview_like', 'edges')
        if self.likes == len(likes_edges):
            # If the Post's metadata already contains all likes, don't do GraphQL requests to obtain them
            yield from (like['node'] for like in likes_edges)
        yield from self._context.graphql_node_list("1cb6ec562846122743b61e492c85999f", {'shortcode': self.shortcode},
                                                   'https://www.instagram.com/p/' + self.shortcode + '/',
                                                   lambda d: d['data']['shortcode_media']['edge_liked_by'])

    def get_location(self) -> Optional[Dict[str, str]]:
        """If the Post has a location, returns a dictionary with fields 'lat' and 'lng'."""
        loc_dict = self._field("location")
        if loc_dict is not None:
            location_json = self._context.get_json("explore/locations/{0}/".format(loc_dict["id"]),
                                                   params={'__a': 1})
            return location_json["location"] if "location" in location_json else location_json['graphql']['location']

    @staticmethod
    def json_encoder(obj) -> Dict[str, Any]:
        """Convert instance of :class:`Post` to a JSON-serializable dictionary."""
        if not isinstance(obj, Post):
            raise TypeError("Object of type {} is not a Post object.".format(obj.__class__.__name__))
        jsondict = {}
        for prop in dir(Post):
            if prop[0].isupper() or prop[0] == '_':
                # skip uppercase and private properties
                continue
            val = obj.__getattribute__(prop)
            if val is True or val is False or isinstance(val, (str, int, float, list)):
                jsondict[prop] = val
            elif isinstance(val, datetime):
                jsondict[prop] = val.isoformat()
        return jsondict


class Profile:
    """
    An Instagram Profile.

    Provides methods for accessing profile properties, as well as :meth:`Profile.get_posts` and for own profile
    :meth:`Profile.get_saved_posts`.

    This class implements == and is hashable.
    """
    def __init__(self, context: InstaloaderContext, profile_name: str):
        """
        Lookup Profile information and create Profile instance.

        :param context: :class:`InstaloaderContext` instance used for queries etc.
        :param identifier: Profile name (string).
        """
        self._context = context

        try:
            metadata = self._context.get_json('{}/'.format(profile_name), params={'__a': 1})
            self._metadata = metadata['graphql'] if 'graphql' in metadata else metadata
        except QueryReturnedNotFoundException:
            raise ProfileNotExistsException('Profile {} does not exist.'.format(profile_name))

    @property
    def userid(self) -> int:
        return int(self._metadata['user']['id'])

    @property
    def username(self) -> str:
        return self._metadata['user']['username']

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
        return self._metadata['user']['is_private']

    @property
    def followed_by_viewer(self) -> bool:
        return self._metadata['user']['followed_by_viewer']

    @property
    def mediacount(self) -> int:
        if "media" in self._metadata["user"]:
            # backwards compatibility with old non-graphql structure
            return self._metadata["user"]["media"]["count"]
        return self._metadata["user"]["edge_owner_to_timeline_media"]["count"]

    @property
    def biography(self) -> str:
        return self._metadata['user']['biography']

    @property
    def blocked_by_viewer(self) -> bool:
        return self._metadata['user']['blocked_by_viewer']

    @property
    def follows_viewer(self) -> bool:
        return self._metadata['user']['follows_viewer']

    @property
    def full_name(self) -> str:
        return self._metadata['user']['full_name']

    @property
    def has_blocked_viewer(self) -> bool:
        return self._metadata['user']['has_blocked_viewer']

    @property
    def has_requested_viewer(self) -> bool:
        return self._metadata['user']['has_requested_viewer']

    @property
    def is_verified(self) -> bool:
        return self._metadata['user']['is_verified']

    @property
    def requested_by_viewer(self) -> bool:
        return self._metadata['user']['requested_by_viewer']

    def get_profile_pic_url(self) -> str:
        """Return URL of profile picture"""
        try:
            with self._context.get_anonymous_session() as anonymous_session:
                data = self._context.get_json(path='api/v1/users/{0}/info/'.format(self.userid), params={},
                                              host='i.instagram.com', session=anonymous_session)
            return data["user"]["hd_profile_pic_url_info"]["url"]
        except (InstaloaderException, KeyError) as err:
            self._context.error('{} Unable to fetch high quality profile pic.'.format(err))
            return self._metadata["user"]["profile_pic_url_hd"] if "profile_pic_url_hd" in self._metadata["user"] \
                else self._metadata["user"]["profile_pic_url"]

    def get_posts(self) -> Iterator[Post]:
        """Retrieve all posts from a profile."""
        if 'media' in self._metadata['user']:
            # backwards compatibility with old non-graphql structure
            yield from (Post(self._context, node, owner_profile=self)
                        for node in self._metadata['user']['media']['nodes'])
            has_next_page = self._metadata['user']['media']['page_info']['has_next_page']
            end_cursor = self._metadata['user']['media']['page_info']['end_cursor']
        else:
            yield from (Post(self._context, edge['node'], owner_profile=self)
                        for edge in self._metadata['user']['edge_owner_to_timeline_media']['edges'])
            has_next_page = self._metadata['user']['edge_owner_to_timeline_media']['page_info']['has_next_page']
            end_cursor = self._metadata['user']['edge_owner_to_timeline_media']['page_info']['end_cursor']
        while has_next_page:
            # We do not use self.graphql_node_list() here, because profile_metadata
            # lets us obtain the first 12 nodes 'for free'
            data = self._context.graphql_query("472f257a40c653c64c666ce877d59d2b",
                                               {'id': self.userid,
                                                'first': GRAPHQL_PAGE_LENGTH,
                                                'after': end_cursor},
                                               'https://www.instagram.com/{0}/'.format(self.username))
            media = data['data']['user']['edge_owner_to_timeline_media']
            yield from (Post(self._context, edge['node'], owner_profile=self)
                        for edge in media['edges'])
            has_next_page = media['page_info']['has_next_page']
            end_cursor = media['page_info']['end_cursor']

    def get_saved_posts(self) -> Iterator[Post]:
        """Get Posts that are marked as saved by the user."""

        if self.username != self._context.username:
            raise LoginRequiredException("--login={} required to get that profile's saved posts.".format(self.username))

        data = self._metadata

        while True:
            if "edge_saved_media" in data["user"]:
                is_edge = True
                saved_media = data["user"]["edge_saved_media"]
            else:
                is_edge = False
                saved_media = data["user"]["saved_media"]

            if is_edge:
                yield from (Post(self._context, edge["node"]) for edge in saved_media["edges"])
            else:
                yield from (Post(self._context, node) for node in saved_media["nodes"])

            if not saved_media["page_info"]["has_next_page"]:
                break
            data = self._context.graphql_query("f883d95537fbcd400f466f63d42bd8a1",
                                               {'id': self.userid, 'first': GRAPHQL_PAGE_LENGTH,
                                                'after': saved_media["page_info"]["end_cursor"]})['data']
