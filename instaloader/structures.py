import json
import lzma
import re
from base64 import b64decode, b64encode
from collections import namedtuple
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional, Union

from . import __version__
from .exceptions import *
from .instaloadercontext import InstaloaderContext


PostSidecarNode = namedtuple('PostSidecarNode', ['is_video', 'display_url', 'video_url'])
PostSidecarNode.__doc__ = "Item of a Sidecar Post."
PostSidecarNode.is_video.__doc__ = "Whether this node is a video."
PostSidecarNode.display_url.__doc__ = "URL of image or video thumbnail."
PostSidecarNode.video_url.__doc__ = "URL of video or None."

PostComment = namedtuple('PostComment', ['id', 'created_at_utc', 'text', 'owner'])
PostComment.id.__doc__ = "ID number of comment."
PostComment.created_at_utc.__doc__ = ":class:`~datetime.datetime` when comment was created (UTC)."
PostComment.text.__doc__ = "Comment text."
PostComment.owner.__doc__ = "Owner :class:`Profile` of the comment."

PostLocation = namedtuple('PostLocation', ['id', 'name', 'slug', 'has_public_page', 'lat', 'lng'])
PostLocation.id.__doc__ = "ID number of location."
PostLocation.name.__doc__ = "Location name."
PostLocation.slug.__doc__ = "URL friendly variant of location name."
PostLocation.has_public_page.__doc__ = "Whether location has a public page."
PostLocation.lat.__doc__ = "Latitude (:class:`float`)."
PostLocation.lng.__doc__ = "Longitude (:class:`float`)."


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
        self._full_metadata_dict = None
        self._rhx_gis_str = None
        self._location = None

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

    def _asdict(self):
        if self._full_metadata_dict:
            node = self._full_metadata_dict
        else:
            node = self._node
        if self._owner_profile:
            node['owner'] = self.owner_profile._asdict()
        if self._location:
            node['location'] = self._location._asdict()
        return node

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

    def _obtain_metadata(self):
        if not self._full_metadata_dict:
            pic_json = self._context.get_json("p/{0}/".format(self.shortcode), params={})
            self._full_metadata_dict = pic_json['entry_data']['PostPage'][0]['graphql']['shortcode_media']
            self._rhx_gis_str = pic_json['rhx_gis']

    @property
    def _full_metadata(self) -> Dict[str, Any]:
        self._obtain_metadata()
        return self._full_metadata_dict

    @property
    def _rhx_gis(self) -> str:
        self._obtain_metadata()
        return self._rhx_gis_str

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
        return self.owner_profile.userid

    @property
    def date_local(self) -> datetime:
        """Timestamp when the post was created (local time zone)."""
        return datetime.fromtimestamp(self._node["date"] if "date" in self._node else self._node["taken_at_timestamp"])

    @property
    def date_utc(self) -> datetime:
        """Timestamp when the post was created (UTC)."""
        return datetime.utcfromtimestamp(self._node["date"] if "date" in self._node else self._node["taken_at_timestamp"])

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
        return self._node["display_url"] if "display_url" in self._node else self._node["display_src"]

    @property
    def typename(self) -> str:
        """Type of post, GraphImage, GraphVideo or GraphSidecar"""
        if '__typename' in self._node:
            return self._node['__typename']
        # if __typename is not in node, it is an old image or video
        return 'GraphImage'

    def get_sidecar_nodes(self) -> Iterator[PostSidecarNode]:
        """Sidecar nodes of a Post with typename==GraphSidecar."""
        if self.typename == 'GraphSidecar':
            for edge in self._field('edge_sidecar_to_children', 'edges'):
                node = edge['node']
                is_video = node['is_video']
                yield PostSidecarNode(is_video=is_video, display_url=node['display_url'],
                                      video_url=node['video_url'] if is_video else None)

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

    def get_comments(self) -> Iterator[PostComment]:
        """Iterate over all comments of the post.

        Each comment is represented by a PostComment namedtuple with fields text (string), created_at (datetime),
        id (int) and owner (:class:`Profile`).
        """
        def _postcomment(node):
            return PostComment(id=int(node['id']),
                               created_at_utc=datetime.utcfromtimestamp(node['created_at']),
                               text=node['text'],
                               owner=Profile(self._context, node['owner']))
        if self.comments == 0:
            # Avoid doing additional requests if there are no comments
            return
        comment_edges = self._field('edge_media_to_comment', 'edges')
        if self.comments == len(comment_edges):
            # If the Post's metadata already contains all comments, don't do GraphQL requests to obtain them
            yield from (_postcomment(comment['node']) for comment in comment_edges)
            return
        yield from (_postcomment(node) for node in
                    self._context.graphql_node_list("33ba35852cb50da46f5b5e889df7d159",
                                                    {'shortcode': self.shortcode},
                                                    'https://www.instagram.com/p/' + self.shortcode + '/',
                                                    lambda d: d['data']['shortcode_media']['edge_media_to_comment'],
                                                    self._rhx_gis))

    def get_likes(self) -> Iterator['Profile']:
        """Iterate over all likes of the post. A :class:`Profile` instance of each likee is yielded."""
        if self.likes == 0:
            # Avoid doing additional requests if there are no comments
            return
        likes_edges = self._field('edge_media_preview_like', 'edges')
        if self.likes == len(likes_edges):
            # If the Post's metadata already contains all likes, don't do GraphQL requests to obtain them
            yield from (Profile(self._context, like['node']) for like in likes_edges)
            return
        yield from (Profile(self._context, node) for node in
                    self._context.graphql_node_list("1cb6ec562846122743b61e492c85999f", {'shortcode': self.shortcode},
                                                    'https://www.instagram.com/p/' + self.shortcode + '/',
                                                    lambda d: d['data']['shortcode_media']['edge_liked_by'],
                                                    self._rhx_gis))

    @property
    def location(self) -> Optional[PostLocation]:
        """If the Post has a location, returns PostLocation namedtuple with fields 'id', 'lat' and 'lng' and 'name'."""
        loc = self._field("location")
        if self._location or not loc:
            return self._location
        location_id = int(loc['id'])
        if any(k not in loc for k in ('name', 'slug', 'has_public_page', 'lat', 'lng')):
            loc = self._context.get_json("explore/locations/{0}/".format(location_id),
                                         params={'__a': 1})['graphql']['location']
        self._location = PostLocation(location_id, loc['name'], loc['slug'], loc['has_public_page'],
                                      loc['lat'], loc['lng'])
        return self._location


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
        self._has_public_story = None
        self._node = node
        self._rhx_gis = None
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
        profile._obtain_metadata()  # to raise ProfileNotExistException now in case username is invalid
        return profile

    @classmethod
    def from_id(cls, context: InstaloaderContext, profile_id: int):
        """Create a Profile instance from a given userid. If possible, use :meth:`Profile.from_username`
        or constructor directly rather than this method, since it does many requests.

        :param context: :attr:`Instaloader.context`
        :param profile_id: userid
        :raises: :class:`ProfileNotExistsException`, :class:`ProfileHasNoPicsException`
        """
        data = context.graphql_query("472f257a40c653c64c666ce877d59d2b",
                                     {'id': str(profile_id), 'first': 1},
                                     rhx_gis=context.root_rhx_gis)['data']['user']
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
        return Post(context, data['edges'][0]['node']).owner_profile

    def _asdict(self):
        json_node = self._node.copy()
        # remove posts
        json_node.pop('edge_media_collections', None)
        json_node.pop('edge_owner_to_timeline_media', None)
        json_node.pop('edge_saved_media', None)
        if self._iphone_struct_:
            json_node['iphone_struct'] = self._iphone_struct_
        return json_node

    def _obtain_metadata(self):
        try:
            if not self._rhx_gis:
                metadata = self._context.get_json('{}/'.format(self.username), params={})
                self._node = metadata['entry_data']['ProfilePage'][0]['graphql']['user']
                self._rhx_gis = metadata['rhx_gis']
        except (QueryReturnedNotFoundException, KeyError) as err:
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
        if not self._iphone_struct_:
            with self._context.anonymous_copy() as anonymous_context:
                data = anonymous_context.get_json(path='api/v1/users/{}/info/'.format(self.userid),
                                                  params={}, host='i.instagram.com')
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
    def followers(self) -> int:
        return self._metadata('edge_followed_by', 'count')

    @property
    def followees(self) -> int:
        return self._metadata('edge_follow', 'count')

    @property
    def external_url(self) -> Optional[str]:
        return self._metadata('external_url')

    @property
    def biography(self) -> str:
        return self._metadata('biography')

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
        This becomes `True` if the :class:`Profile` has any stories currently available,
        even if not viewable by the viewer.
        """
        return self._iphone_struct['has_highlight_reels']

    @property
    def has_public_story(self) -> bool:
        if not self._has_public_story:
            self._obtain_metadata()
            # query not rate limited if invoked anonymously:
            with self._context.anonymous_copy() as anonymous_context:
                data = anonymous_context.graphql_query('9ca88e465c3f866a76f7adee3871bdd8',
                                                       {'user_id': self.userid, 'include_chaining': False,
                                                        'include_reel': False, 'include_suggested_users': False,
                                                        'include_logged_out_extras': True,
                                                        'include_highlight_reels': False},
                                                       'https://www.instagram.com/{}/'.format(self.username),
                                                       self._rhx_gis)
            self._has_public_story = data['data']['user']['has_public_story']
        return self._has_public_story

    @property
    def has_viewable_story(self) -> bool:
        """
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
        """Return URL of profile picture"""
        try:
            return self._iphone_struct['hd_profile_pic_url_info']['url']
        except (InstaloaderException, KeyError) as err:
            self._context.error('{} Unable to fetch high quality profile pic.'.format(err))
            return self._metadata("profile_pic_url_hd")

    def get_profile_pic_url(self) -> str:
        """.. deprecated:: 4.0.3

	   Use :attr:`profile_pic_url`."""
        return self.profile_pic_url

    def get_posts(self) -> Iterator[Post]:
        """Retrieve all posts from a profile."""
        self._obtain_metadata()
        yield from (Post(self._context, node, self) for node in
                    self._context.graphql_node_list("472f257a40c653c64c666ce877d59d2b",
                                                    {'id': self.userid},
                                                    'https://www.instagram.com/{0}/'.format(self.username),
                                                    lambda d: d['data']['user']['edge_owner_to_timeline_media'],
                                                    self._rhx_gis,
                                                    self._metadata('edge_owner_to_timeline_media')))

    def get_saved_posts(self) -> Iterator[Post]:
        """Get Posts that are marked as saved by the user."""

        if self.username != self._context.username:
            raise LoginRequiredException("--login={} required to get that profile's saved posts.".format(self.username))

        self._obtain_metadata()
        yield from (Post(self._context, node) for node in
                    self._context.graphql_node_list("f883d95537fbcd400f466f63d42bd8a1",
                                                    {'id': self.userid},
                                                    'https://www.instagram.com/{0}/'.format(self.username),
                                                    lambda d: d['data']['user']['edge_saved_media'],
                                                    self._rhx_gis,
                                                    self._metadata('edge_saved_media')))

    def get_followers(self) -> Iterator['Profile']:
        """
        Retrieve list of followers of given profile.
        To use this, one needs to be logged in and private profiles has to be followed.
        """
        if not self._context.is_logged_in:
            raise LoginRequiredException("--login required to get a profile's followers.")
        self._obtain_metadata()
        yield from (Profile(self._context, node) for node in
                    self._context.graphql_node_list("37479f2b8209594dde7facb0d904896a",
                                                    {'id': str(self.userid)},
                                                    'https://www.instagram.com/' + self.username + '/',
                                                    lambda d: d['data']['user']['edge_followed_by'],
                                                    self._rhx_gis))

    def get_followees(self) -> Iterator['Profile']:
        """
        Retrieve list of followees (followings) of given profile.
        To use this, one needs to be logged in and private profiles has to be followed.
        """
        if not self._context.is_logged_in:
            raise LoginRequiredException("--login required to get a profile's followees.")
        self._obtain_metadata()
        yield from (Profile(self._context, node) for node in
                    self._context.graphql_node_list("58712303d941c6855d4e888c5f0cd22f",
                                                    {'id': str(self.userid)},
                                                    'https://www.instagram.com/' + self.username + '/',
                                                    lambda d: d['data']['user']['edge_follow'],
                                                    self._rhx_gis))


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

    def _asdict(self):
        node = self._node
        if self._owner_profile:
            node['owner'] = self._owner_profile._asdict()
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

    @property
    def owner_profile(self) -> Profile:
        """:class:`Profile` instance of the story item's owner."""
        if not self._owner_profile:
            self._owner_profile = Profile.from_id(self._context, self._node['owner']['id'])
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
        """Timestamp when the StoryItem was created (local time zone)."""
        return datetime.fromtimestamp(self._node['taken_at_timestamp'])

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
        return self._node['display_resources'][-1]['src']

    @property
    def typename(self) -> str:
        """Type of post, GraphStoryImage or GraphStoryVideo"""
        return self._node['__typename']

    @property
    def is_video(self) -> bool:
        """True if the StoryItem is a video."""
        return self._node['is_video']

    @property
    def video_url(self) -> Optional[str]:
        """URL of the video, or None."""
        if self.is_video:
            return self._node['video_resources'][-1]['src']


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
               L.download_storyitem(item, ':stores')

    This class implements == and is hashable.

    :param context: :class:`InstaloaderContext` instance used for additional queries if necessary.
    :param node: Dictionary containing the available information of the story as returned by Instagram.
    """

    def __init__(self, context: InstaloaderContext, node: Dict[str, Any]):
        self._context = context
        self._node = node
        self._unique_id = None
        self._owner_profile = None

    def __repr__(self):
        return '<Story by {} changed {:%Y-%m-%d_%H-%M-%S_UTC}>'.format(self.owner_username, self.latest_media_utc)

    def __eq__(self, o: object) -> bool:
        if isinstance(o, Story):
            return self.unique_id == o.unique_id
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._unique_id)

    @property
    def unique_id(self) -> str:
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
        """Timestamp when the story has last been watched or None (local time zone)."""
        if self._node['seen']:
            return datetime.fromtimestamp(self._node['seen'])

    @property
    def last_seen_utc(self) -> Optional[datetime]:
        """Timestamp when the story has last been watched or None (UTC)."""
        if self._node['seen']:
            return datetime.utcfromtimestamp(self._node['seen'])

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

    def get_items(self) -> Iterator[StoryItem]:
        """Retrieve all items from a story."""
        yield from (StoryItem(self._context, item, self.owner_profile) for item in reversed(self._node['items']))


JsonExportable = Union[Post, Profile, StoryItem]


def save_structure_to_file(structure: JsonExportable, filename: str) -> None:
    """Saves a :class:`Post`, :class:`Profile` or :class:`StoryItem` to a '.json' or '.json.xz' file such that it can
    later be loaded by :func:`load_structure_from_file`.

    If the specified filename ends in '.xz', the file will be LZMA compressed. Otherwise, a pretty-printed JSON file
    will be created.

    :param structure: :class:`Post`, :class:`Profile` or :class:`StoryItem`
    :param filename: Filename, ends in '.json' or '.json.xz'
    """
    json_structure = {'node': structure._asdict(),
                      'instaloader': {'version': __version__, 'node_type': structure.__class__.__name__}}
    compress = filename.endswith('.xz')
    if compress:
        with lzma.open(filename, 'wt', check=lzma.CHECK_NONE) as fp:
            json.dump(json_structure, fp=fp, separators=(',', ':'))
    else:
        with open(filename, 'wt') as fp:
            json.dump(json_structure, fp=fp, indent=4, sort_keys=True)


def load_structure_from_file(context: InstaloaderContext, filename: str) -> JsonExportable:
    """Loads a :class:`Post`, :class:`Profile` or :class:`StoryItem` from a '.json' or '.json.xz' file that
    has been saved by :func:`save_structure_to_file`.

    :param context: :attr:`Instaloader.context` linked to the new object, used for additional queries if neccessary.
    :param filename: Filename, ends in '.json' or '.json.xz'
    """
    compressed = filename.endswith('.xz')
    if compressed:
        fp = lzma.open(filename, 'rt')
    else:
        fp = open(filename, 'rt')
    json_structure = json.load(fp)
    fp.close()
    if 'node' in json_structure and 'instaloader' in json_structure and \
            'node_type' in json_structure['instaloader']:
        node_type = json_structure['instaloader']['node_type']
        if node_type == "Post":
            return Post(context, json_structure['node'])
        elif node_type == "Profile":
            return Profile(context, json_structure['node'])
        elif node_type == "StoryItem":
            return StoryItem(context, json_structure['node'])
        else:
            raise InvalidArgumentException("{}: Not an Instaloader JSON.".format(filename))
    elif 'shortcode' in json_structure:
        # Post JSON created with Instaloader v3
        return Post.from_shortcode(context, json_structure['shortcode'])
    else:
        raise InvalidArgumentException("{}: Not an Instaloader JSON.".format(filename))
