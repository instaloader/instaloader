"""Download pictures (or videos) along with their captions and other metadata from Instagram."""


__version__ = '4.0.3'


try:
    # pylint:disable=wrong-import-position
    import win_unicode_console
except ImportError:
    pass
else:
    win_unicode_console.enable()

from .exceptions import *
from .instaloader import Instaloader
from .instaloadercontext import InstaloaderContext
from .structures import (Post, PostSidecarNode, PostComment, PostLocation, Profile, Story, StoryItem,
                         load_structure_from_file, save_structure_to_file)
