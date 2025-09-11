from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Literal, Optional, TypeVar

from mininterface import Optional, Tag, Validation
from mininterface.tag.flag import Blank
from tyro.conf import (DisallowNone, FlagCreatePairsOff, OmitArgPrefixes,
                       Positional, arg, configure)

from .instaloader import (get_default_session_filename,
                          get_default_stamps_filename)
from .instaloadercontext import default_user_agent

T = TypeVar("T")
NoHint = Annotated[T, arg(help_behavior_hint="")]


@dataclass
class PostDownloadOptions:
    """
    What to Download of each Post
    """

    slide: NoHint[Optional[str]] = None
    """Set what image/interval of a sidecar you want to download."""

    no_pictures: NoHint[bool] = False
    """Do not download post pictures. Cannot be used together with --fast-update.
    Implies --no-video-thumbnails, does not imply --no-videos.
    """

    no_videos: Annotated[bool, arg(aliases=["-V"], help_behavior_hint="")] = False
    """Do not download videos."""

    no_video_thumbnails: NoHint[bool] = False
    """Do not download thumbnails of videos."""

    geotags: Annotated[bool, arg(aliases=["-G"], help_behavior_hint="")] = False
    """Download geotags when available. Geotags are stored as a text file with the location's name and a Google Maps link.
    This requires an additional request to the Instagram server for each picture. Requires login.
    """

    comments: Annotated[bool, arg(aliases=["-C"], help_behavior_hint="")] = False
    """Download and update comments for each post. Requires an additional request to the Instagram server for each post.
    Disabled by default. Requires login.
    """

    no_captions: NoHint[bool] = False
    """Do not create txt files."""

    post_metadata_txt: NoHint[list[str]] = field(default_factory=list)
    """Template to write in txt file for each Post."""

    storyitem_metadata_txt: NoHint[list[str]] = field(default_factory=list)
    """Template to write in txt file for each StoryItem."""

    no_metadata_json: NoHint[bool] = False
    """Do not create a JSON file containing the metadata of each post."""

    no_compress_json: NoHint[bool] = False
    """Do not xz compress JSON files, rather create pretty formatted JSONs."""


@dataclass
class ProfileDownloadOptions:
    """
    What to Download of each Profile
    """

    no_posts: NoHint[bool] = False
    """Do not download regular posts."""

    no_profile_pic: NoHint[bool] = False
    """Do not download profile picture."""

    stories: Annotated[NoHint[bool], arg(aliases=["-s"])] = False
    """Also download stories of each profile that is downloaded. Requires login."""

    highlights: NoHint[bool] = False
    """Also download highlights of each profile that is downloaded. Requires login."""

    tagged: NoHint[bool] = False
    """Also download posts where each profile is tagged."""

    reels: NoHint[bool] = False
    """Also download Reels videos."""

    igtv: NoHint[bool] = False
    """Also download IGTV videos."""

    stories_only: NoHint[bool] = False

    profile_pic_only: Annotated[bool, arg(aliases=["-P"], help_behavior_hint="")] = (
        False
    )


@dataclass
class ConditionOptions:
    """
    Which Posts to Download
    """

    fast_update: Annotated[bool, arg(aliases=["-F"], help_behavior_hint="")] = False
    """For each target, stop when encountering the first already-downloaded picture.
    Recommended when you use Instaloader to update your personal Instagram archive.
    """

    latest_stamps: Annotated[
        Blank[Path], Literal[Path(get_default_stamps_filename())]
    ] = None
    """Store the timestamps of latest media scraped for each profile.
    Allows updating your personal Instagram archive even if you delete the destination directories.
    """

    post_filter: Annotated[
        Optional[str], arg(aliases=["--only-if"], help_behavior_hint="")
    ] = None
    """Expression that, if given, must evaluate to True for each post to be downloaded.
    Must be a syntactically valid python expression. Variables are evaluated to instaloader.Post attributes.
    Example: --post-filter=viewer_has_liked.
    """

    storyitem_filter: NoHint[Optional[str]] = None
    """Expression that, if given, must evaluate to True for each storyitem to be downloaded.
    Must be a syntactically valid python expression. Variables are evaluated to instaloader.StoryItem attributes.
    """

    count: Annotated[Optional[str], arg(aliases=["-c"], help_behavior_hint="")] = None
    """Do not attempt to download more than COUNT posts. Applies to #hashtag, %location_id, :feed, and :saved.
    """


@dataclass
class LoginOptions:
    """
    Login (Download Private Profiles)

    Instaloader can login to Instagram. This allows downloading private profiles.
    To login, pass the --login option. Your session cookie (not your password!)
    will be saved to a local file to be reused next time you want Instaloader
    to login. Instead of --login, the --load-cookies option can be used to
    import a session from a browser.
    """

    login: Annotated[Optional[str], arg(aliases=["-l"], help_behavior_hint="")] = None
    """Login name (profile name) for your Instagram account."""

    load_cookies: Annotated[
        Optional[str], arg(aliases=["-b"], help_behavior_hint="")
    ] = None
    """Browser name to load cookies from Instagram."""

    cookiefile: Annotated[
        Optional[Path], arg(aliases=["-B"], help_behavior_hint="")
    ] = None
    """Cookie file of a profile to load cookies."""

    sessionfile: Annotated[
        Optional[Path],
        arg(
            aliases=["-f"],
            help_behavior_hint="",
            help=f"""Path for loading and storing session key file. Defaults to {get_default_session_filename("<login_name>")}.""",
        ),
    ] = None

    password: Annotated[Optional[str], arg(aliases=["-p"], help_behavior_hint="")] = (
        None
    )
    """Password for your Instagram account. Without this option, you'll be prompted interactively
    if there is not yet a valid session file."""


def http_status_check(codes: Tag[list[int] | None]):
    if codes.val is None:
        return True
    for code in codes.val:
        if not 100 <= code <= 599:
            return f"Invalid HTTP status code: {code}"
    return True


@dataclass
class DownloadOptions:
    """
    How to Download
    """

    dirname_pattern: NoHint[Optional[str]] = None
    """Name of directory where to store posts. {profile} is replaced by the profile name, {target} is replaced
    by the target you specified, i.e. either :feed, #hashtag or the profile name. Defaults to '{target}'.
    """

    filename_pattern: Annotated[Optional[str], arg(help_behavior_hint="")] = None
    """Prefix of filenames for posts and stories, relative to the directory given with --dirname-pattern.
    {profile} is replaced by the profile name, {target} is replaced by the target you specified.
    Defaults to '{date_utc}_UTC'.
    """

    title_pattern: Annotated[Optional[str], arg(help_behavior_hint="")] = None
    """Prefix of filenames for profile pics, hashtag profile pics, and highlight covers.
    Defaults to '{date_utc}_UTC_{typename}' if --dirname-pattern contains '{target}' or '{dirname}',
    or if --dirname-pattern is not specified. Otherwise defaults to
    '{target}_{date_utc}_UTC_{typename}'.
    """

    resume_prefix: Annotated[Optional[str], arg(help_behavior_hint="")] = None
    """Prefix for filenames that are used to save the information to resume an interrupted download."""

    sanitize_paths: NoHint[bool] = False
    """Sanitize paths so that resulting file and directory names are valid on both Windows and Unix."""

    no_resume: NoHint[bool] = False
    """Do not resume a previously-aborted download iteration, and do not save such information when interrupted."""

    use_aged_resume_files: NoHint[bool] = False

    user_agent: str = default_user_agent()
    """User Agent to use for HTTP requests."""

    no_sleep: Annotated[bool, arg(aliases=["-S"], help_behavior_hint="")] = False

    max_connection_attempts: int = 3
    """Maximum number of connection attempts until a request is aborted.
    If a connection fails, it can be manually skipped by hitting CTRL+C. Set to 0 to retry infinitely.
    """

    request_timeout: float = 300.0
    """Seconds to wait before timing out a connection request."""

    abort_on: Annotated[
        Optional[list[int]], arg(help_behavior_hint=""), Validation(http_status_check)
    ] = None
    """Comma-separated list of HTTP status codes that cause Instaloader to abort, bypassing all retry logic."""

    no_iphone: NoHint[bool] = False
    """Do not attempt to download iPhone version of images and videos."""


@dataclass
@configure(DisallowNone, FlagCreatePairsOff, OmitArgPrefixes)
class Env:
    """
    Download pictures (or videos) along with their captions and other metadata from Instagram.
    """

    targets: Positional[list[str]]
    """
    Specify a list of targets. For each of these, Instaloader creates a folder
    and downloads all posts. The following targets are supported.

      * profile             Download profile. If an already-downloaded profile has been renamed, Instaloader automatically finds it by its unique ID and renames the folder likewise.
      * @profile            Download all followees of profile. Requires login. Consider using :feed rather than @yourself.
      * #hashtag            Download #hashtag.
      * %location_id        Download %%location_id. Requires login.
      * :feed               Download pictures from your feed. Requires login.
      * :stories            Download the stories of your followees. Requires login.
      * :saved              Download the posts that you marked as saved. Requires login.
      * -- -shortcode       Download the post with the given shortcode
      * filename.json[.xz]  Re-Download the given object.
      * +args.txt           Read targets (and options) from given textfile.
    """

    post: PostDownloadOptions
    profile: ProfileDownloadOptions
    conditions: ConditionOptions
    login: LoginOptions
    download: DownloadOptions
