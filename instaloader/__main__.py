"""Download pictures (or videos) along with their captions and other metadata from Instagram."""

import ast
import datetime
import logging
import os
import re
import sys
from argparse import ArgumentTypeError
from enum import IntEnum
from pathlib import Path
from typing import List, Optional

from mininterface import run

from . import (AbortDownloadException, BadCredentialsException, Instaloader,
               InstaloaderException, InvalidArgumentException, LoginException,
               Post, Profile, ProfileNotExistsException, StoryItem,
               TwoFactorAuthRequiredException, __version__,
               load_structure_from_file)
from .cli import Env
from .lateststamps import LatestStamps

try:
    import browser_cookie3
    bc3_library = True
except ImportError:
    bc3_library = False

logger = logging.getLogger(__name__)
class ExitCode(IntEnum):
    SUCCESS = 0
    NON_FATAL_ERROR = 1
    INIT_FAILURE = 2
    LOGIN_FAILURE = 3
    DOWNLOAD_ABORTED = 4
    USER_ABORTED = 5
    UNEXPECTED_ERROR = 99

def usage_string():
    # NOTE: duplicated in README.rst and docs/index.rst
    argv0 = os.path.basename(sys.argv[0])
    argv0 = "instaloader" if argv0 == "__main__.py" else argv0
    return """
{0} [--comments] [--geotags]
{2:{1}} [--stories] [--highlights] [--tagged] [--reels] [--igtv]
{2:{1}} [--login YOUR-USERNAME] [--fast-update]
{2:{1}} profile | "#hashtag" | %%location_id | :stories | :feed | :saved
{0} --help""".format(argv0, len(argv0), '')

# TODO remove
def http_status_code_list(code_list_str: str) -> List[int]:
    codes = [int(s) for s in code_list_str.split(',')]
    for code in codes:
        if not 100 <= code <= 599:
            raise ArgumentTypeError("Invalid HTTP status code: {}".format(code))
    return codes


def filterstr_to_filterfunc(filter_str: str, item_type: type):
    """Takes an --post-filter=... or --storyitem-filter=... filter
     specification and makes a filter_func Callable out of it."""

    # The filter_str is parsed, then all names occurring in its AST are replaced by loads to post.<name>. A
    # function Post->bool is returned which evaluates the filter with the post as 'post' in its namespace.

    class TransformFilterAst(ast.NodeTransformer):
        def visit_Name(self, node: ast.Name):
            if not isinstance(node.ctx, ast.Load):
                raise InvalidArgumentException("Invalid filter: Modifying variables ({}) not allowed.".format(node.id))
            if node.id == "datetime":
                return node
            if not hasattr(item_type, node.id):
                raise InvalidArgumentException("Invalid filter: {} not a {} attribute.".format(node.id,
                                                                                               item_type.__name__))
            new_node = ast.Attribute(ast.copy_location(ast.Name('item', ast.Load()), node), node.id,
                                     ast.copy_location(ast.Load(), node))
            return ast.copy_location(new_node, node)

    input_filename = '<command line filter parameter>'
    compiled_filter = compile(TransformFilterAst().visit(ast.parse(filter_str, filename=input_filename, mode='eval')),
                              filename=input_filename, mode='eval')

    def filterfunc(item) -> bool:
        # pylint:disable=eval-used
        return bool(eval(compiled_filter, {'item': item, 'datetime': datetime.datetime}))

    return filterfunc


def get_cookies_from_instagram(domain, browser, cookie_file='', cookie_name=''):
    supported_browsers = {
        "brave": browser_cookie3.brave,
        "chrome": browser_cookie3.chrome,
        "chromium": browser_cookie3.chromium,
        "edge": browser_cookie3.edge,
        "firefox": browser_cookie3.firefox,
        "librewolf": browser_cookie3.librewolf,
        "opera": browser_cookie3.opera,
        "opera_gx": browser_cookie3.opera_gx,
        "safari": browser_cookie3.safari,
        "vivaldi": browser_cookie3.vivaldi,
    }

    if browser not in supported_browsers:
        raise InvalidArgumentException("Loading cookies from the specified browser failed\n"
                                       "Supported browsers are Brave, Chrome, Chromium, Edge, Firefox, LibreWolf, "
                                       "Opera, Opera_GX, Safari and Vivaldi")

    cookies = {}
    browser_cookies = list(supported_browsers[browser](cookie_file=cookie_file))

    for cookie in browser_cookies:
        if domain in cookie.domain:
            cookies[cookie.name] = cookie.value

    if cookies:
        print(f"Cookies loaded successfully from {browser}")
    else:
        raise LoginException(f"No cookies found for Instagram in {browser}, "
                             f"Are you logged in successfully in {browser}?")

    if cookie_name:
        return cookies.get(cookie_name, {})
    else:
        return cookies


def import_session(browser, instaloader, cookiefile):
    cookie = get_cookies_from_instagram('instagram', browser, cookiefile)
    if cookie is not None:
        instaloader.context.update_cookies(cookie)
        username = instaloader.test_login()
        if not username:
            raise LoginException(f"Not logged in. Are you logged in successfully in {browser}?")
        instaloader.context.username = username
        print(f"{username} has been successfully logged in.")
        print(f"Next time use --login={username} to reuse the same session.")


def _main(instaloader: Instaloader, targetlist: List[str],
          username: Optional[str] = None, password: Optional[str] = None,
          sessionfile: Optional[str] = None,
          download_profile_pic: bool = True, download_posts=True,
          download_stories: bool = False,
          download_highlights: bool = False,
          download_tagged: bool = False,
          download_reels: bool = False,
          download_igtv: bool = False,
          fast_update: bool = False,
          latest_stamps_file: Optional[str] = None,
          max_count: Optional[int] = None, post_filter_str: Optional[str] = None,
          storyitem_filter_str: Optional[str] = None,
          browser: Optional[str] = None,
          cookiefile: Optional[str] = None) -> ExitCode:
    """Download set of profiles, hashtags etc. and handle logging in and session files if desired."""
    # Parse and generate filter function
    post_filter = None
    if post_filter_str is not None:
        post_filter = filterstr_to_filterfunc(post_filter_str, Post)
        instaloader.context.log('Only download posts with property "{}".'.format(post_filter_str))
    storyitem_filter = None
    if storyitem_filter_str is not None:
        storyitem_filter = filterstr_to_filterfunc(storyitem_filter_str, StoryItem)
        instaloader.context.log('Only download storyitems with property "{}".'.format(storyitem_filter_str))
    latest_stamps = None
    if latest_stamps_file is not None:
        latest_stamps = LatestStamps(latest_stamps_file)
        instaloader.context.log(f"Using latest stamps from {latest_stamps_file}.")
    # load cookies if browser is not None
    if browser and bc3_library:
        import_session(browser.lower(), instaloader, cookiefile)
    elif browser and not bc3_library:
        raise InvalidArgumentException("browser_cookie3 library is needed to load cookies from browsers")
    # Login, if desired
    if username is not None:
        if not re.match(r"^[A-Za-z0-9._]+$", username):
            instaloader.context.error("Warning: Parameter \"{}\" for --login is not a valid username.".format(username))
        try:
            instaloader.load_session_from_file(username, sessionfile)
        except FileNotFoundError as err:
            if sessionfile is not None:
                print(err, file=sys.stderr)
            instaloader.context.log("Session file does not exist yet - Logging in.")
        if not instaloader.context.is_logged_in or username != instaloader.test_login():
            if password is not None:
                try:
                    instaloader.login(username, password)
                except TwoFactorAuthRequiredException:
                    # https://github.com/instaloader/instaloader/issues/1217
                    instaloader.context.error("Warning: There have been reports of 2FA currently not working. "
                                              "Consider importing session cookies from your browser with "
                                              "--load-cookies.")
                    while True:
                        try:
                            code = input("Enter 2FA verification code: ")
                            instaloader.two_factor_login(code)
                            break
                        except BadCredentialsException as err:
                            print(err, file=sys.stderr)
                            pass
            else:
                try:
                    instaloader.interactive_login(username)
                except KeyboardInterrupt:
                    print("\nInterrupted by user.", file=sys.stderr)
                    return ExitCode.USER_ABORTED
        instaloader.context.log("Logged in as %s." % username)
    # since 4.2.9 login is required for geotags
    if instaloader.download_geotags and not instaloader.context.is_logged_in:
        instaloader.context.error("Warning: Login is required to download geotags of posts.")
    # Try block for KeyboardInterrupt (save session on ^C)
    profiles = set()
    anonymous_retry_profiles = set()
    exit_code = ExitCode.SUCCESS
    try:
        # Generate set of profiles, already downloading non-profile targets
        for target in targetlist:
            if (target.endswith('.json') or target.endswith('.json.xz')) and os.path.isfile(target):
                with instaloader.context.error_catcher(target):
                    structure = load_structure_from_file(instaloader.context, target)
                    if isinstance(structure, Post):
                        if post_filter is not None and not post_filter(structure):
                            instaloader.context.log("<{} ({}) skipped>".format(structure, target), flush=True)
                            continue
                        instaloader.context.log("Downloading {} ({})".format(structure, target))
                        instaloader.download_post(structure, os.path.dirname(target))
                    elif isinstance(structure, StoryItem):
                        if storyitem_filter is not None and not storyitem_filter(structure):
                            instaloader.context.log("<{} ({}) skipped>".format(structure, target), flush=True)
                            continue
                        instaloader.context.log("Attempting to download {} ({})".format(structure, target))
                        instaloader.download_storyitem(structure, os.path.dirname(target))
                    elif isinstance(structure, Profile):
                        raise InvalidArgumentException("Profile JSON are ignored. Pass \"{}\" to download that profile"
                                                       .format(structure.username))
                    else:
                        raise InvalidArgumentException("{} JSON file not supported as target"
                                                       .format(structure.__class__.__name__))
                continue
            # strip '/' characters to be more shell-autocompletion-friendly
            target = target.rstrip('/')
            with instaloader.context.error_catcher(target):
                if re.match(r"^@[A-Za-z0-9._]+$", target):
                    instaloader.context.log("Retrieving followees of %s..." % target[1:])
                    profile = Profile.from_username(instaloader.context, target[1:])
                    for followee in profile.get_followees():
                        instaloader.save_profile_id(followee)
                        profiles.add(followee)
                elif re.match(r"^#\w+$", target):
                    instaloader.download_hashtag(hashtag=target[1:], max_count=max_count, fast_update=fast_update,
                                                 post_filter=post_filter,
                                                 profile_pic=download_profile_pic, posts=download_posts)
                elif re.match(r"^-[A-Za-z0-9-_]+$", target):
                    instaloader.download_post(Post.from_shortcode(instaloader.context, target[1:]), target)
                elif re.match(r"^%[0-9]+$", target):
                    instaloader.download_location(location=target[1:], max_count=max_count, fast_update=fast_update,
                                                  post_filter=post_filter)
                elif target == ":feed":
                    instaloader.download_feed_posts(fast_update=fast_update, max_count=max_count,
                                                    post_filter=post_filter)
                elif target == ":stories":
                    instaloader.download_stories(fast_update=fast_update, storyitem_filter=storyitem_filter)
                elif target == ":saved":
                    instaloader.download_saved_posts(fast_update=fast_update, max_count=max_count,
                                                     post_filter=post_filter)
                elif re.match(r"^[A-Za-z0-9._]+$", target):
                    download_profile_content = download_posts or download_tagged or download_reels or download_igtv
                    try:
                        profile = instaloader.check_profile_id(target, latest_stamps)
                        if instaloader.context.is_logged_in and profile.has_blocked_viewer:
                            if download_profile_pic or (
                                download_profile_content and not profile.is_private
                            ):
                                raise ProfileNotExistsException("{} blocked you; But we download her anonymously."
                                                                .format(target))
                            else:
                                instaloader.context.error("{} blocked you.".format(target))
                        else:
                            profiles.add(profile)
                    except ProfileNotExistsException as err:
                        # Not only our profile.has_blocked_viewer condition raises ProfileNotExistsException,
                        # check_profile_id() also does, since access to blocked profile may be responded with 404.
                        if instaloader.context.is_logged_in and (download_profile_pic or download_profile_content):
                            instaloader.context.log(err)
                            instaloader.context.log("Trying again anonymously, helps in case you are just blocked.")
                            with instaloader.anonymous_copy() as anonymous_loader:
                                with instaloader.context.error_catcher():
                                    anonymous_retry_profiles.add(anonymous_loader.check_profile_id(target,
                                                                                                   latest_stamps))
                                    instaloader.context.error("Warning: {} will be downloaded anonymously (\"{}\")."
                                                              .format(target, err))
                        else:
                            raise
                else:
                    target_type = {
                        '#': 'hashtag',
                        '%': 'location',
                        '-': 'shortcode',
                    }.get(target[0], 'username')
                    raise ProfileNotExistsException('Invalid {} {}'.format(target_type, target))
        if len(profiles) > 1:
            instaloader.context.log("Downloading {} profiles: {}".format(len(profiles),
                                                                         ' '.join([p.username for p in profiles])))
        if instaloader.context.iphone_support and profiles and (download_profile_pic or download_posts) and \
           not instaloader.context.is_logged_in:
            instaloader.context.log("Hint: Login to download higher-quality versions of pictures.")
        instaloader.download_profiles(
            profiles,
            download_profile_pic,
            download_posts,
            download_tagged,
            download_igtv,
            download_highlights,
            download_stories,
            fast_update,
            post_filter,
            storyitem_filter,
            latest_stamps=latest_stamps,
            reels=download_reels,
        )
        if anonymous_retry_profiles:
            instaloader.context.log("Downloading anonymously: {}"
                                    .format(' '.join([p.username for p in anonymous_retry_profiles])))
            with instaloader.anonymous_copy() as anonymous_loader:
                anonymous_loader.download_profiles(
                    anonymous_retry_profiles,
                    download_profile_pic,
                    download_posts,
                    download_tagged,
                    download_igtv,
                    fast_update=fast_update,
                    post_filter=post_filter,
                    latest_stamps=latest_stamps,
                    reels=download_reels
                )
    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)
        exit_code = ExitCode.USER_ABORTED
    except AbortDownloadException as exc:
        print("\nDownload aborted: {}.".format(exc), file=sys.stderr)
        exit_code = ExitCode.DOWNLOAD_ABORTED
    # Save session if it is useful
    if instaloader.context.is_logged_in:
        instaloader.save_session_to_file(sessionfile)
    # User might be confused if Instaloader does nothing
    if not targetlist:
        if instaloader.context.is_logged_in:
            # Instaloader did at least save a session file
            instaloader.context.log("No targets were specified, thus nothing has been downloaded.")
        else:
            # Instaloader did not do anything
            instaloader.context.log("usage:" + usage_string())
            exit_code = ExitCode.INIT_FAILURE
    return exit_code


def main():
    m = run(Env, description=__doc__,  usage=usage_string(),
                        epilog="The complete documentation can be found at "
                                "https://instaloader.github.io/.",
                        fromfile_prefix_chars='+', ask_on_empty_cli=True, add_version=__version__, add_quiet=True, allow_abbrev=True)
    args = m.env

    # miniterface takes care of the commen flags like --quiet, hence we determine the quietness from the system logger
    quiet = logger.getEffectiveLevel() == logging.ERROR

    try:
        if (args.login.login is None and args.login.load_cookies is None) and (args.profile.stories or args.profile.stories_only):
            print("Login is required to download stories.", file=sys.stderr)
            args.profile.stories = False
            if args.profile.stories_only:
                raise InvalidArgumentException()

        if ':feed-all' in args.targets or ':feed-liked' in args.targets:
            raise InvalidArgumentException(":feed-all and :feed-liked were removed. Use :feed as target and "
                                           "eventually --post-filter=viewer_has_liked.")

        post_metadata_txt_pattern = '\n'.join(args.post.post_metadata_txt) if args.post.post_metadata_txt else None
        storyitem_metadata_txt_pattern = '\n'.join(args.post.storyitem_metadata_txt) if args.post.storyitem_metadata_txt else None

        if args.post.no_captions:
            if not (post_metadata_txt_pattern or storyitem_metadata_txt_pattern):
                post_metadata_txt_pattern = ''
                storyitem_metadata_txt_pattern = ''
            else:
                raise InvalidArgumentException("--no-captions and --post-metadata-txt or --storyitem-metadata-txt "
                                               "given; That contradicts.")

        if args.download.no_resume and args.download.resume_prefix:
            raise InvalidArgumentException("--no-resume and --resume-prefix given; That contradicts.")
        resume_prefix = (args.download.resume_prefix if args.download.resume_prefix else 'iterator') if not args.download.no_resume else None

        if args.post.no_pictures and args.conditions.fast_update:
            raise InvalidArgumentException('--no-pictures and --fast-update cannot be used together.')

        if args.login.login and args.login.load_cookies:
            raise InvalidArgumentException('--load-cookies and --login cannot be used together.')

        # Determine what to download
        download_profile_pic = not args.profile.no_profile_pic or args.profile.profile_pic_only
        download_posts = not (args.profile.no_posts or args.profile.stories_only or args.profile.profile_pic_only)
        download_stories = args.profile.stories or args.profile.stories_only

        def path_to_str(path: Optional[Path]):
            # Using Path instead of str brings benefits, user file dialog. However the original code still needs a str|None, hence we cast it back.
            return path and str(path)

        loader = Instaloader(sleep=not args.download.no_sleep, quiet=quiet, user_agent=args.download.user_agent,
                             dirname_pattern=args.download.dirname_pattern, filename_pattern=args.download.filename_pattern,
                             download_pictures=not args.post.no_pictures,
                             download_videos=not args.post.no_videos, download_video_thumbnails=not args.post.no_video_thumbnails,
                             download_geotags=args.post.geotags,
                             download_comments=args.post.comments, save_metadata=not args.post.no_metadata_json,
                             compress_json=not args.post.no_compress_json,
                             post_metadata_txt_pattern=post_metadata_txt_pattern,
                             storyitem_metadata_txt_pattern=storyitem_metadata_txt_pattern,
                             max_connection_attempts=args.download.max_connection_attempts,
                             request_timeout=args.download.request_timeout,
                             resume_prefix=resume_prefix,
                             check_resume_bbd=not args.download.use_aged_resume_files,
                             slide=args.post.slide,
                             fatal_status_codes=args.download.abort_on,
                             iphone_support=not args.download.no_iphone,
                             title_pattern=args.download.title_pattern,
                             sanitize_paths=args.download.sanitize_paths)

        exit_code = _main(loader,
                          args.targets,
                          username=args.login.login.lower() if args.login.login is not None else None,
                          password=args.login.password,
                          sessionfile=path_to_str(args.login.sessionfile),
                          download_profile_pic=download_profile_pic,
                          download_posts=download_posts,
                          download_stories=download_stories,
                          download_highlights=args.profile.highlights,
                          download_tagged=args.profile.tagged,
                          download_reels=args.profile.reels,
                          download_igtv=args.profile.igtv,
                          fast_update=args.conditions.fast_update,
                          latest_stamps_file=path_to_str(args.conditions.latest_stamps),
                          max_count=int(args.conditions.count) if args.conditions.count is not None else None,
                          post_filter_str=args.conditions.post_filter,
                          storyitem_filter_str=args.conditions.storyitem_filter,
                          browser=args.login.load_cookies,
                          cookiefile=path_to_str(args.login.cookiefile))

        loader.close()
        if loader.has_stored_errors:
            exit_code = ExitCode.NON_FATAL_ERROR
    except InvalidArgumentException as err:
        print(err, file=sys.stderr)
        exit_code = ExitCode.INIT_FAILURE
    except LoginException as err:
        print(err, file=sys.stderr)
        exit_code = ExitCode.LOGIN_FAILURE
    except InstaloaderException as err:
        print("Fatal error: %s" % err)
        exit_code = ExitCode.UNEXPECTED_ERROR
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
