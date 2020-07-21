"""Download pictures (or videos) along with their captions and other metadata from Instagram."""

import ast
import datetime
import os
import re
import sys
from argparse import ArgumentParser, SUPPRESS
from typing import List, Optional

from . import (Instaloader, InstaloaderException, InvalidArgumentException, Post, Profile, ProfileNotExistsException,
               StoryItem, __version__, load_structure_from_file, TwoFactorAuthRequiredException,
               BadCredentialsException)
from .instaloader import get_default_session_filename
from .instaloadercontext import default_user_agent


def usage_string():
    # NOTE: duplicated in README.rst and docs/index.rst
    argv0 = os.path.basename(sys.argv[0])
    argv0 = "instaloader" if argv0 == "__main__.py" else argv0
    return """
{0} [--comments] [--geotags]
{2:{1}} [--stories] [--highlights] [--tagged] [--igtv]
{2:{1}} [--login YOUR-USERNAME] [--fast-update]
{2:{1}} profile | "#hashtag" | %%location_id | :stories | :feed | :saved
{0} --help""".format(argv0, len(argv0), '')


def filterstr_to_filterfunc(filter_str: str, item_type: type):
    """Takes an --post-filter=... or --storyitem-filter=... filter
     specification and makes a filter_func Callable out of it."""

    # The filter_str is parsed, then all names occurring in its AST are replaced by loads to post.<name>. A
    # function Post->bool is returned which evaluates the filter with the post as 'post' in its namespace.

    class TransformFilterAst(ast.NodeTransformer):
        def visit_Name(self, node: ast.Name):
            # pylint:disable=no-self-use
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


def _main(instaloader: Instaloader, targetlist: List[str],
          username: Optional[str] = None, password: Optional[str] = None,
          sessionfile: Optional[str] = None,
          download_profile_pic: bool = True, download_posts=True,
          download_stories: bool = False,
          download_highlights: bool = False,
          download_tagged: bool = False,
          download_igtv: bool = False,
          fast_update: bool = False,
          max_count: Optional[int] = None, post_filter_str: Optional[str] = None,
          storyitem_filter_str: Optional[str] = None) -> None:
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
                    while True:
                        try:
                            code = input("Enter 2FA verification code: ")
                            instaloader.two_factor_login(code)
                            break
                        except BadCredentialsException:
                            pass
            else:
                instaloader.interactive_login(username)
        instaloader.context.log("Logged in as %s." % username)
    # since 4.2.9 login is required for geotags
    if instaloader.download_geotags and not instaloader.context.is_logged_in:
        instaloader.context.error("Warning: Use --login to download geotags of posts.")
    # Try block for KeyboardInterrupt (save session on ^C)
    profiles = set()
    anonymous_retry_profiles = set()
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
                    try:
                        profile = instaloader.check_profile_id(target)
                        if instaloader.context.is_logged_in and profile.has_blocked_viewer:
                            if download_profile_pic or ((download_posts or download_tagged or download_igtv)
                                                        and not profile.is_private):
                                raise ProfileNotExistsException("{} blocked you; But we download her anonymously."
                                                                .format(target))
                            else:
                                instaloader.context.error("{} blocked you.".format(target))
                        else:
                            profiles.add(profile)
                    except ProfileNotExistsException as err:
                        # Not only our profile.has_blocked_viewer condition raises ProfileNotExistsException,
                        # check_profile_id() also does, since access to blocked profile may be responded with 404.
                        if instaloader.context.is_logged_in and (download_profile_pic or download_posts or
                                                                 download_tagged or download_igtv):
                            instaloader.context.log(err)
                            instaloader.context.log("Trying again anonymously, helps in case you are just blocked.")
                            with instaloader.anonymous_copy() as anonymous_loader:
                                with instaloader.context.error_catcher():
                                    anonymous_retry_profiles.add(anonymous_loader.check_profile_id(target))
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
        if profiles and (download_profile_pic or download_posts) and not instaloader.context.is_logged_in:
            instaloader.context.error("Warning: Use --login to download higher-quality versions of pictures.")
        instaloader.download_profiles(profiles,
                                      download_profile_pic, download_posts, download_tagged, download_igtv,
                                      download_highlights, download_stories,
                                      fast_update, post_filter, storyitem_filter)
        if anonymous_retry_profiles:
            instaloader.context.log("Downloading anonymously: {}"
                                    .format(' '.join([p.username for p in anonymous_retry_profiles])))
            with instaloader.anonymous_copy() as anonymous_loader:
                anonymous_loader.download_profiles(anonymous_retry_profiles,
                                                   download_profile_pic, download_posts, download_tagged, download_igtv,
                                                   fast_update=fast_update, post_filter=post_filter)
    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)
    # Save session if it is useful
    if instaloader.context.is_logged_in:
        instaloader.save_session_to_file(sessionfile)
    # User might be confused if Instaloader does nothing
    if not targetlist:
        if instaloader.context.is_logged_in:
            # Instaloader did at least save a session file
            instaloader.context.log("No targets were specified, thus nothing has been downloaded.")
        else:
            # Instloader did not do anything
            instaloader.context.log("usage:" + usage_string())


def main():
    parser = ArgumentParser(description=__doc__, add_help=False, usage=usage_string(),
                            epilog="Report issues at https://github.com/instaloader/instaloader/issues. "
                                   "The complete documentation can be found at "
                                   "https://instaloader.github.io/.",
                            fromfile_prefix_chars='+')

    g_targets = parser.add_argument_group("What to Download",
                                          "Specify a list of targets. For each of these, Instaloader creates a folder "
                                          "and downloads all posts. The following targets are supported:")
    g_targets.add_argument('profile', nargs='*',
                           help="Download profile. If an already-downloaded profile has been renamed, Instaloader "
                                "automatically finds it by its unique ID and renames the folder likewise.")
    g_targets.add_argument('_at_profile', nargs='*', metavar="@profile",
                           help="Download all followees of profile. Requires --login. "
                                "Consider using :feed rather than @yourself.")
    g_targets.add_argument('_hashtag', nargs='*', metavar='"#hashtag"', help="Download #hashtag.")
    g_targets.add_argument('_location', nargs='*', metavar='%location_id',
                           help="Download %%location_id. Requires --login.")
    g_targets.add_argument('_feed', nargs='*', metavar=":feed",
                           help="Download pictures from your feed. Requires --login.")
    g_targets.add_argument('_stories', nargs='*', metavar=":stories",
                           help="Download the stories of your followees. Requires --login.")
    g_targets.add_argument('_saved', nargs='*', metavar=":saved",
                           help="Download the posts that you marked as saved. Requires --login.")
    g_targets.add_argument('_singlepost', nargs='*', metavar="-- -shortcode",
                           help="Download the post with the given shortcode")
    g_targets.add_argument('_json', nargs='*', metavar="filename.json[.xz]",
                           help="Re-Download the given object.")
    g_targets.add_argument('_fromfile', nargs='*', metavar="+args.txt",
                           help="Read targets (and options) from given textfile.")

    g_post = parser.add_argument_group("What to Download of each Post")

    g_prof = parser.add_argument_group("What to Download of each Profile")

    g_prof.add_argument('-P', '--profile-pic-only', action='store_true',
                        help=SUPPRESS)
    g_prof.add_argument('--no-posts', action='store_true',
                        help="Do not download regular posts.")
    g_prof.add_argument('--no-profile-pic', action='store_true',
                        help='Do not download profile picture.')
    g_post.add_argument('--no-pictures', action='store_true',
                        help='Do not download post pictures. Cannot be used together with --fast-update. '
                             'Implies --no-video-thumbnails, does not imply --no-videos.')
    g_post.add_argument('-V', '--no-videos', action='store_true',
                        help='Do not download videos.')
    g_post.add_argument('--no-video-thumbnails', action='store_true',
                        help='Do not download thumbnails of videos.')
    g_post.add_argument('-G', '--geotags', action='store_true',
                        help='Download geotags when available. Geotags are stored as a '
                             'text file with the location\'s name and a Google Maps link. '
                             'This requires an additional request to the Instagram '
                             'server for each picture. Requires --login.')
    g_post.add_argument('-C', '--comments', action='store_true',
                        help='Download and update comments for each post. '
                             'This requires an additional request to the Instagram '
                             'server for each post, which is why it is disabled by default.')
    g_post.add_argument('--no-captions', action='store_true',
                        help='Do not create txt files.')
    g_post.add_argument('--post-metadata-txt', action='append',
                        help='Template to write in txt file for each Post.')
    g_post.add_argument('--storyitem-metadata-txt', action='append',
                        help='Template to write in txt file for each StoryItem.')
    g_post.add_argument('--no-metadata-json', action='store_true',
                        help='Do not create a JSON file containing the metadata of each post.')
    g_post.add_argument('--metadata-json', action='store_true',
                        help=SUPPRESS)
    g_post.add_argument('--no-compress-json', action='store_true',
                        help='Do not xz compress JSON files, rather create pretty formatted JSONs.')
    g_prof.add_argument('-s', '--stories', action='store_true',
                        help='Also download stories of each profile that is downloaded. Requires --login.')
    g_prof.add_argument('--stories-only', action='store_true',
                        help=SUPPRESS)
    g_prof.add_argument('--highlights', action='store_true',
                        help='Also download highlights of each profile that is downloaded. Requires --login.')
    g_prof.add_argument('--tagged', action='store_true',
                        help='Also download posts where each profile is tagged.')
    g_prof.add_argument('--igtv', action='store_true',
                        help='Also download IGTV videos.')

    g_cond = parser.add_argument_group("Which Posts to Download")

    g_cond.add_argument('-F', '--fast-update', action='store_true',
                        help='For each target, stop when encountering the first already-downloaded picture. This '
                             'flag is recommended when you use Instaloader to update your personal Instagram archive.')

    g_cond.add_argument('--post-filter', '--only-if', metavar='filter',
                        help='Expression that, if given, must evaluate to True for each post to be downloaded. Must be '
                             'a syntactically valid python expression. Variables are evaluated to '
                             'instaloader.Post attributes. Example: --post-filter=viewer_has_liked.')
    g_cond.add_argument('--storyitem-filter', metavar='filter',
                        help='Expression that, if given, must evaluate to True for each storyitem to be downloaded. '
                             'Must be a syntactically valid python expression. Variables are evaluated to '
                             'instaloader.StoryItem attributes.')

    g_cond.add_argument('-c', '--count',
                        help='Do not attempt to download more than COUNT posts. '
                             'Applies only to #hashtag and :feed.')

    g_login = parser.add_argument_group('Login (Download Private Profiles)',
                                        'Instaloader can login to Instagram. This allows downloading private profiles. '
                                        'To login, pass the --login option. Your session cookie (not your password!) '
                                        'will be saved to a local file to be reused next time you want Instaloader '
                                        'to login.')
    g_login.add_argument('-l', '--login', metavar='YOUR-USERNAME',
                         help='Login name (profile name) for your Instagram account.')
    g_login.add_argument('-f', '--sessionfile',
                         help='Path for loading and storing session key file. '
                              'Defaults to ' + get_default_session_filename("<login_name>"))
    g_login.add_argument('-p', '--password', metavar='YOUR-PASSWORD',
                         help='Password for your Instagram account. Without this option, '
                              'you\'ll be prompted for your password interactively if '
                              'there is not yet a valid session file.')

    g_how = parser.add_argument_group('How to Download')
    g_how.add_argument('--dirname-pattern',
                       help='Name of directory where to store posts. {profile} is replaced by the profile name, '
                            '{target} is replaced by the target you specified, i.e. either :feed, #hashtag or the '
                            'profile name. Defaults to \'{target}\'.')
    g_how.add_argument('--filename-pattern',
                       help='Prefix of filenames, relative to the directory given with '
                            '--dirname-pattern. {profile} is replaced by the profile name,'
                            '{target} is replaced by the target you specified, i.e. either :feed'
                            '#hashtag or the profile name. Defaults to \'{date_utc}_UTC\'')
    g_how.add_argument('--resume-prefix', metavar='PREFIX',
                       help='Prefix for filenames that are used to save the information to resume an interrupted '
                            'download.')
    g_how.add_argument('--no-resume', action='store_true',
                       help='Do not resume a previously-aborted download iteration, and do not save such information '
                            'when interrupted.')
    g_how.add_argument('--use-aged-resume-files', action='store_true', help=SUPPRESS)
    g_how.add_argument('--user-agent',
                       help='User Agent to use for HTTP requests. Defaults to \'{}\'.'.format(default_user_agent()))
    g_how.add_argument('-S', '--no-sleep', action='store_true', help=SUPPRESS)
    g_how.add_argument('--max-connection-attempts', metavar='N', type=int, default=3,
                       help='Maximum number of connection attempts until a request is aborted. Defaults to 3. If a '
                            'connection fails, it can be manually skipped by hitting CTRL+C. Set this to 0 to retry '
                            'infinitely.')
    g_how.add_argument('--commit-mode', action='store_true', help=SUPPRESS)
    g_how.add_argument('--request-timeout', metavar='N', type=float,
                       help='seconds to wait before timing out a connection request')

    g_misc = parser.add_argument_group('Miscellaneous Options')
    g_misc.add_argument('-q', '--quiet', action='store_true',
                        help='Disable user interaction, i.e. do not print messages (except errors) and fail '
                             'if login credentials are needed but not given. This makes Instaloader suitable as a '
                             'cron job.')
    g_misc.add_argument('-h', '--help', action='help', help='Show this help message and exit.')
    g_misc.add_argument('--version', action='version', help='Show version number and exit.',
                        version=__version__)

    args = parser.parse_args()
    try:
        if args.login is None and (args.stories or args.stories_only):
            print("--login=USERNAME required to download stories.", file=sys.stderr)
            args.stories = False
            if args.stories_only:
                raise SystemExit(1)

        if ':feed-all' in args.profile or ':feed-liked' in args.profile:
            raise SystemExit(":feed-all and :feed-liked were removed. Use :feed as target and "
                             "eventually --post-filter=viewer_has_liked.")

        post_metadata_txt_pattern = '\n'.join(args.post_metadata_txt) if args.post_metadata_txt else None
        storyitem_metadata_txt_pattern = '\n'.join(args.storyitem_metadata_txt) if args.storyitem_metadata_txt else None

        if args.no_captions:
            if not (post_metadata_txt_pattern or storyitem_metadata_txt_pattern):
                post_metadata_txt_pattern = ''
                storyitem_metadata_txt_pattern = ''
            else:
                raise SystemExit("--no-captions and --post-metadata-txt or --storyitem-metadata-txt given; "
                                 "That contradicts.")

        if args.no_resume and args.resume_prefix:
            raise SystemExit("--no-resume and --resume-prefix given; That contradicts.")
        resume_prefix = (args.resume_prefix if args.resume_prefix else 'iterator') if not args.no_resume else None

        if args.no_pictures and args.fast_update:
            raise SystemExit('--no-pictures and --fast-update cannot be used together.')

        # Determine what to download
        download_profile_pic = not args.no_profile_pic or args.profile_pic_only
        download_posts = not (args.no_posts or args.stories_only or args.profile_pic_only)
        download_stories = args.stories or args.stories_only

        loader = Instaloader(sleep=not args.no_sleep, quiet=args.quiet, user_agent=args.user_agent,
                             dirname_pattern=args.dirname_pattern, filename_pattern=args.filename_pattern,
                             download_pictures=not args.no_pictures,
                             download_videos=not args.no_videos, download_video_thumbnails=not args.no_video_thumbnails,
                             download_geotags=args.geotags,
                             download_comments=args.comments, save_metadata=not args.no_metadata_json,
                             compress_json=not args.no_compress_json,
                             post_metadata_txt_pattern=post_metadata_txt_pattern,
                             storyitem_metadata_txt_pattern=storyitem_metadata_txt_pattern,
                             max_connection_attempts=args.max_connection_attempts,
                             request_timeout=args.request_timeout,
                             resume_prefix=resume_prefix,
                             check_resume_bbd=not args.use_aged_resume_files)
        _main(loader,
              args.profile,
              username=args.login.lower() if args.login is not None else None,
              password=args.password,
              sessionfile=args.sessionfile,
              download_profile_pic=download_profile_pic,
              download_posts=download_posts,
              download_stories=download_stories,
              download_highlights=args.highlights,
              download_tagged=args.tagged,
              download_igtv=args.igtv,
              fast_update=args.fast_update,
              max_count=int(args.count) if args.count is not None else None,
              post_filter_str=args.post_filter,
              storyitem_filter_str=args.storyitem_filter)
        loader.close()
    except InstaloaderException as err:
        raise SystemExit("Fatal error: %s" % err)


if __name__ == "__main__":
    main()
