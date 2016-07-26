#!/usr/bin/env python3

import re, json, datetime, shutil, os, time, random, sys, pickle, getpass
from argparse import ArgumentParser
import requests, requests.utils

DEFAULTSESSIONFILE = "/tmp/.instaloadersession"

class InstaloaderException(Exception):
    """Base exception for this script"""
    pass

class NonfatalException(InstaloaderException):
    """Base exception for errors which should not cause instaloader to stop"""
    pass

class ProfileNotExistsException(NonfatalException):
    pass

class ProfileHasNoPicsException(NonfatalException):
    pass

class PrivateProfileNotFollowedException(NonfatalException):
    pass

class LoginRequiredException(NonfatalException):
    pass

class BadCredentialsException(InstaloaderException):
    pass

class ConnectionException(InstaloaderException):
    pass


def log(*msg, sep='', end='\n', flush=False, quiet=False):
    if not quiet:
        print(*msg, sep=sep, end=end, flush=flush)

def get_json(name, session, max_id=0, sleep_min_max=[1,5]):
    resp = session.get('http://www.instagram.com/'+name, \
        params={'max_id': max_id})
    time.sleep(abs(sleep_min_max[1]-sleep_min_max[0])*random.random()+abs(sleep_min_max[0]))
    match = re.search('window\._sharedData = .*<', resp.text)
    if match is None:
        return None
    else:
        return json.loads(match.group(0)[21:-2])

def get_last_id(data):
    if len(data["entry_data"]) == 0 or \
        len(data["entry_data"]["ProfilePage"][0]["user"]["media"]["nodes"]) == 0:
        return None
    else:
        data = data["entry_data"]["ProfilePage"][0]["user"]["media"]["nodes"]
        return int(data[len(data)-1]["id"])

def epoch_to_string(epoch):
    return datetime.datetime.fromtimestamp(epoch).strftime('%Y-%m-%d_%H-%M-%S')

def get_file_extension(url):
    match = re.search('\.[a-z]*\?', url)
    if match is None:
        return url[-3:]
    else:
        return match.group(0)[1:-1]

def download_pic(name, url, date_epoch, outputlabel=None, quiet=False):
    # Returns true, if file was actually downloaded, i.e. updated
    if outputlabel is None:
        outputlabel = epoch_to_string(date_epoch)
    filename = name.lower() + '/' + epoch_to_string(date_epoch) + '.' + get_file_extension(url)
    if os.path.isfile(filename):
        log(outputlabel + ' exists', end='  ', flush=True, quiet=quiet)
        return False
    resp = get_anonymous_session().get(url, stream=True)
    if resp.status_code == 200:
        log(outputlabel, end='  ', flush=True, quiet=quiet)
        os.makedirs(name.lower(), exist_ok=True)
        with open(filename, 'wb') as file:
            resp.raw.decode_content = True
            shutil.copyfileobj(resp.raw, file)
        os.utime(filename, (datetime.datetime.now().timestamp(), date_epoch))
        return True
    else:
        raise ConnectionException("file \'" + url + "\' could not be downloaded")

def save_caption(name, date_epoch, caption, quiet=False):
    filename = name.lower() + '/' + epoch_to_string(date_epoch) + '.txt'
    if os.path.isfile(filename):
        with open(filename, 'r') as file:
            file_caption = file.read()
        if file_caption == caption:
            log('txt unchanged', end=' ', flush=True, quiet=quiet)
            return None
        else:
            def get_filename(index):
                return filename if index==0 else (filename[:-4] + '_old_' + \
                        (str(0) if index<10 else str()) + str(index) + filename[-4:])
            i = 0
            while os.path.isfile(get_filename(i)):
                i = i + 1
            for index in range(i, 0, -1):
                os.rename(get_filename(index-1), get_filename(index))
            log('txt updated', end=' ', flush=True, quiet=quiet)
    log('txt', end=' ', flush=True, quiet=quiet)
    os.makedirs(name.lower(), exist_ok=True)
    with open(filename, 'w') as text_file:
        text_file.write(caption)
    os.utime(filename, (datetime.datetime.now().timestamp(), date_epoch))

def download_profilepic(name, url, quiet=False):
    date_object = datetime.datetime.strptime(requests.head(url).headers["Last-Modified"], \
        '%a, %d %b %Y %H:%M:%S GMT')
    filename = name.lower() + '/' + epoch_to_string(date_object.timestamp()) + \
        '_UTC_profile_pic.' + url[-3:]
    if os.path.isfile(filename):
        log(filename + ' already exists', quiet=quiet)
        return None
    match = re.search('http.*://.*instagram.*[^/]*\.(com|net)/[^/]+/.', url)
    if match is None:
        raise ConnectionException("url \'" + url + "\' could not be processed")
    index = len(match.group(0))-1
    offset = 8 if match.group(0)[-1:] == 's' else 0
    url = url[:index] + 's2048x2048' + ('/' if offset == 0 else str()) + url[index+offset:]
    resp = get_anonymous_session().get(url, stream=True)
    if resp.status_code == 200:
        log(filename, quiet=quiet)
        os.makedirs(name.lower(), exist_ok=True)
        with open(filename, 'wb') as file:
            resp.raw.decode_content = True
            shutil.copyfileobj(resp.raw, file)
        os.utime(filename, (datetime.datetime.now().timestamp(), date_object.timestamp()))
    else:
        raise ConnectionException("file \'" + url + "\' could not be downloaded")

def save_session(session, filename, quiet=False):
    if filename is None:
        filename = DEFAULTSESSIONFILE
    with open(filename, 'wb') as sessionfile:
        os.chmod(filename, 0o600)
        pickle.dump(requests.utils.dict_from_cookiejar(session.cookies), sessionfile)
        log("Saved session to %s." % filename, quiet=quiet)

def load_session(filename, quiet=False):
    if filename is None:
        filename = DEFAULTSESSIONFILE
    try:
        with open(filename, 'rb') as sessionfile:
            session = requests.Session()
            session.cookies = requests.utils.cookiejar_from_dict(pickle.load(sessionfile))
            session.headers.update(default_http_header())
            log("Loaded session from %s." % filename, quiet=quiet)
            return session
    except FileNotFoundError:
        pass

def test_login(user, session):
    if user is None or session is None:
        return False
    resp = session.get('https://www.instagram.com/')
    time.sleep(4 * random.random() + 1)
    return resp.text.find(user.lower()) != -1

def default_http_header(empty_session_only=False):
    user_agent = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 ' \
                '(KHTML, like Gecko) Chrome/51.0.2704.79 Safari/537.36'
    header = {  'Accept-Encoding' : 'gzip, deflate', \
                'Accept-Language' : 'en-US,en;q=0.8', \
                'Connection' : 'keep-alive', \
                'Content-Length' : '0', \
                'Host' : 'www.instagram.com', \
                'Origin' : 'https://www.instagram.com', \
                'Referer' : 'https://www.instagram.com/', \
                'User-Agent' : user_agent, \
                'X-Instagram-AJAX' : '1', \
                'X-Requested-With' : 'XMLHttpRequest'}
    if empty_session_only:
        del header['Host']
        del header['Origin']
        del header['Referer']
        del header['X-Instagram-AJAX']
        del header['X-Requested-With']
    return header

def get_anonymous_session():
    session = requests.Session()
    session.cookies.update({'sessionid' : '', 'mid' : '', 'ig_pr' : '1', \
                                 'ig_vw' : '1920', 'csrftoken' : '', \
                                       's_network' : '', 'ds_user_id' : ''})
    session.headers.update(default_http_header(empty_session_only=True))
    return session

def get_session(user, passwd):
    """Log in to instagram with given username and password and return session object"""
    session = requests.Session()
    session.cookies.update({'sessionid' : '', 'mid' : '', 'ig_pr' : '1', \
                                 'ig_vw' : '1920', 'csrftoken' : '', \
                                       's_network' : '', 'ds_user_id' : ''})
    session.headers.update(default_http_header())
    resp = session.get('https://www.instagram.com/')
    session.headers.update({'X-CSRFToken':resp.cookies['csrftoken']})
    time.sleep(9 * random.random() + 3)
    login = session.post('https://www.instagram.com/accounts/login/ajax/', \
            data={'password':passwd,'username':user}, allow_redirects=True)
    session.headers.update({'X-CSRFToken':login.cookies['csrftoken']})
    time.sleep(5 * random.random())
    if login.status_code == 200:
        if test_login(user, session):
            return session
        else:
            raise BadCredentialsException('Login error! Check your credentials!')
    else:
        raise ConnectionException('Login error! Connection error!')

def download(name, session, profile_pic_only=False, download_videos=True,
        fast_update=False, sleep_min_max=[0.25,2], quiet=False):
    """Download one profile"""
    # pylint:disable=too-many-arguments
    # Get profile main page json
    data = get_json(name, session)
    if len(data["entry_data"]) == 0 or "ProfilePage" not in data["entry_data"]:
        raise ProfileNotExistsException("profile %s does not exist" % name)
    # Download profile picture
    download_profilepic(name, data["entry_data"]["ProfilePage"][0]["user"]["profile_pic_url"],
            quiet=quiet)
    time.sleep(abs(sleep_min_max[1]-sleep_min_max[0])*random.random()+abs(sleep_min_max[0]))
    if profile_pic_only:
        return
    # Catch some errors
    if data["entry_data"]["ProfilePage"][0]["user"]["is_private"]:
        if data["config"]["viewer"] is None:
            raise LoginRequiredException("profile %s requires login" % name)
        if not data["entry_data"]["ProfilePage"][0]["user"]["followed_by_viewer"]:
            raise PrivateProfileNotFollowedException("user %s: private but not followed" % name)
    else:
        if data["config"]["viewer"] is not None:
            log("profile %s could also be downloaded anonymously." % name, quiet=quiet)
    if ("nodes" not in data["entry_data"]["ProfilePage"][0]["user"]["media"] or
            len(data["entry_data"]["ProfilePage"][0]["user"]["media"]["nodes"]) == 0) \
                    and not profile_pic_only:
        raise ProfileHasNoPicsException("profile %s: no pics found" % name)
    # Iterate over pictures and download them
    totalcount = data["entry_data"]["ProfilePage"][0]["user"]["media"]["count"]
    count = 1
    while get_last_id(data) is not None:
        for node in data["entry_data"]["ProfilePage"][0]["user"]["media"]["nodes"]:
            log("[%3i/%3i] " % (count, totalcount), end="", flush=True, quiet=quiet)
            count = count + 1
            downloaded = download_pic(name, node["display_src"], node["date"], quiet=quiet)
            time.sleep(abs(sleep_min_max[1]-sleep_min_max[0])*random.random() + \
                       abs(sleep_min_max[0]))
            if "caption" in node:
                save_caption(name, node["date"], node["caption"], quiet=quiet)
            if node["is_video"] and download_videos:
                video_data = get_json('p/' + node["code"], session)
                download_pic(name, \
                        video_data['entry_data']['PostPage'][0]['media']['video_url'], \
                        node["date"], 'mp4', quiet=quiet)
            log(quiet=quiet)
            if fast_update and not downloaded:
                return
        data = get_json(name, session, max_id=get_last_id(data))
        time.sleep(abs(sleep_min_max[1]-sleep_min_max[0])*random.random()+abs(sleep_min_max[0]))

def get_logged_in_session(username, password=None, quiet=False):
    """Logs in and returns session, asking user for password if needed"""
    if password is not None:
        return get_session(username, password)
    if quiet:
        raise LoginRequiredException("Quiet mode requires given password or valid "
                "session file.")
    while password is None:
        password = getpass.getpass(prompt="Enter Instagram password for %s: " % username)
        try:
            return get_session(username, password)
        except BadCredentialsException as err:
            print(err, file=sys.stderr)
            password = None

def download_profiles(targets, username=None, password=None, sessionfile=None,
        profile_pic_only=False, download_videos=True, fast_update=False,
        sleep_min_max=[0.25,2], quiet=False):
    """Download set of profiles and handle sessions"""
    # pylint:disable=too-many-arguments
    # Login, if desired
    if username is not None:
        session = load_session(sessionfile, quiet=quiet)
        if not test_login(username, session):
            session = get_logged_in_session(username, password, quiet)
        log("Logged in as %s." % username, quiet=quiet)
    else:
        session = get_anonymous_session()
    # Iterate through targets list and download them
    failedtargets = []
    try:
        for target in targets:
            try:
                download(target, session, profile_pic_only, download_videos,
                        fast_update, sleep_min_max, quiet)
            except NonfatalException as err:
                failedtargets.append(target)
                print(err, file=sys.stderr)
    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)
    if len(targets) > 1 and len(failedtargets) > 0:
        print("Errors occured (see above) while downloading profiles: %s" %
                ", ".join(failedtargets), file=sys.stderr)
    # Save session if it is useful
    if username is not None:
        save_session(session, sessionfile, quiet=quiet)

def main():
    parser = ArgumentParser(description='Simple downloader to fetch all Instagram pics and '\
                                        'captions from a given profile')
    parser.add_argument('targets', nargs='+', help='Names of profiles to download')
    parser.add_argument('-l', '--login', metavar='login_name',
            help='Provide login name for your Instagram account')
    parser.add_argument('-p', '--password',
            help='Provide password for your Instagram account')
    parser.add_argument('-f', '--sessionfile',
            help='File to store session key, defaults to '+DEFAULTSESSIONFILE)
    parser.add_argument('-P', '--profile-pic-only', action='store_true',
            help='Only download profile picture')
    parser.add_argument('-V', '--skip-videos', action='store_true',
            help='Do not download videos')
    parser.add_argument('-F', '--fast-update', action='store_true',
            help='Abort at encounter of first already-downloaded picture')
    parser.add_argument('-S', '--no-sleep', action='store_true',
            help='Do not sleep between actual downloads of pictures')
    parser.add_argument('-q', '--quiet', action='store_true',
            help='Disable user interaction, i.e. do not print messages (except errors) and fail ' \
                    'if login credentials are needed but not given.')
    args = parser.parse_args()
    try:
        download_profiles(args.targets, args.login, args.password, args.sessionfile,
                args.profile_pic_only, not args.skip_videos, args.fast_update,
                [0,0] if args.no_sleep else [0.25,2], args.quiet)
    except InstaloaderException as err:
        raise SystemExit("Fatal error: %s" % err)

if __name__ == "__main__":
    main()
