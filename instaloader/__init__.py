"""Download pictures (or videos) along with their captions and other metadata from Instagram."""


__version__ = '4.10'


try:
    # pylint:disable=wrong-import-position
    import win_unicode_console  # type: ignore
except ImportError:
    pass
else:
    win_unicode_console.enable()

from .exceptions import *
from .instaloader import Instaloader
from .instaloadercontext import InstaloaderContext, RateController
from .lateststamps import LatestStamps
from .nodeiterator import NodeIterator, FrozenNodeIterator, resumable_iteration
from .structures import (Hashtag, Highlight, Post, PostSidecarNode, PostComment, PostCommentAnswer, PostLocation,
                         Profile, Story, StoryItem, TopSearchResults, load_structure_from_file, save_structure_to_file,
                         load_structure, get_json_structure)
