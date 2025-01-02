"""Download pictures (or videos) along with their captions and other metadata from Instagram."""


__version__ = '4.14'


try:
    # pylint:disable=wrong-import-position
    import win_unicode_console  # type: ignore
except ImportError:
    pass
else:
    win_unicode_console.enable()

from .exceptions import *
from .instaloader import Instaloader as Instaloader
from .instaloadercontext import (InstaloaderContext as InstaloaderContext,
                                 RateController as RateController)
from .lateststamps import LatestStamps as LatestStamps
from .nodeiterator import (NodeIterator as NodeIterator,
                           FrozenNodeIterator as FrozenNodeIterator,
                           resumable_iteration as resumable_iteration)
from .structures import (Hashtag as Hashtag,
                         Highlight as Highlight,
                         Post as Post,
                         PostSidecarNode as PostSidecarNode,
                         PostComment as PostComment,
                         PostCommentAnswer as PostCommentAnswer,
                         PostLocation as PostLocation,
                         Profile as Profile,
                         Story as Story,
                         StoryItem as StoryItem,
                         TopSearchResults as TopSearchResults,
                         TitlePic as TitlePic,
                         load_structure_from_file as load_structure_from_file,
                         save_structure_to_file as save_structure_to_file,
                         load_structure as load_structure,
                         get_json_structure as get_json_structure)
