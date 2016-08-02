#!/usr/bin/env python3

import re, json, datetime, shutil, os, time, random, sys, pickle, getpass, tempfile
from argparse import ArgumentParser
from io import BytesIO
import requests, requests.utils

try:
    import win_unicode_console
except ImportError:
    WINUNICODE = False
else:
    win_unicode_console.enable()
    WINUNICODE = True

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

def get_username_by_id(session, profile_id):
    tempsession = copy_session(session)
    tempsession.headers.update({'Content-Type' : 'application/json'})
    resp = tempsession.post('https://www.instagram.com/query/', data='q=ig_user(' +
                            str(profile_id) +')+%7B%0A++username%0A%7D%0A')
    if resp.status_code == 200:
        data = json.loads(resp.text)
        if 'username' in data:
            return json.loads(resp.text)['username']
        raise ProfileNotExistsException("No profile found, the user may have blocked " +
                                            "you (id: " + str(profile_id) + ").")
    else:
        if test_login(session):
            raise ConnectionException("Username could not be determined due to connection error" +
                                        " (id: "+ str(profile_id) +").")
        raise LoginRequiredException("Login required to determine username (id: " +
                                        str(profile_id) + ").")

def get_id_by_username(profile):
    data = get_json(profile, get_anonymous_session())
    if len(data["entry_data"]) == 0 or "ProfilePage" not in data("entry_data"):
        raise ProfileNotExistsException("Profile {0} does not exist.".format(profile))
    return int(data['entry_data']['ProfilePage'][0]['user']['id'])

def epoch_to_string(epoch):
    return datetime.datetime.fromtimestamp(epoch).strftime('%Y-%m-%d_%H-%M-%S')

def get_file_extension(url):
    match = re.search('\.[a-z]*\?', url)
    if match is None:
        return url[-3:]
    else:
        return match.group(0)[1:-1]

def get_followees(profile, session):
    tmpsession = copy_session(session)
    data = get_json(profile, tmpsession)
    profile_id = data['entry_data']['ProfilePage'][0]['user']['id']
    query = ["q=ig_user(" + profile_id + ")+%7B%0A"
             "++follows.",
             str(data['entry_data']['ProfilePage'][0]['user']['follows']['count']) +
             ")+%7B%0A"
             "++++count%2C%0A"
             "++++page_info+%7B%0A"
             "++++++end_cursor%2C%0A"
             "++++++has_next_page%0A"
             "++++%7D%2C%0A"
             "++++nodes+%7B%0A"
             "++++++id%2C%0A"
             "++++++full_name%2C%0A"
             "++++++username%2C%0A"
             "++++++followed_by+%7B%0A"
             "++++++++count%0A"
             "++++++%7D%0A"
             "++++%7D%0A"
             "++%7D%0A"
             "%7D%0A"
             "&ref=relationships%3A%3Afollow_list"]
    tmpsession.headers.update(default_http_header())
    tmpsession.headers.update({'Referer' : 'https://www.instagram.com/'+profile+'/following/'})
    tmpsession.headers.update({'Content-Type' : 'application/json'})
    resp = tmpsession.post('https://www.instagram.com/query/', data=query[0]+"first("+query[1])
    if resp.status_code == 200:
        data = json.loads(resp.text)
        followees = []
        while True:
            for followee in data['follows']['nodes']:
                followee['follower_count'] = followee.pop('followed_by')['count']
                followees = followees + [followee]
            if data['follows']['page_info']['has_next_page']:
                resp = tmpsession.post('https://www.instagram.com/query/', data=query[0]
                                            + "after("
                                            + data['follows']['page_info']['end_cursor']
                                            + "%2C+" + query[1] )
                data = json.loads(resp.text)
            else:
                break
        return followees
    if test_login(tmpsession):
        raise ConnectionException("ConnectionError("+str(resp.status_code)+"): "
                                  "unable to gather followees.")
    raise LoginRequiredException("Login required to gather followees.")

def download_pic(name, url, date_epoch, outputlabel=None, quiet=False):
    # Returns true, if file was actually downloaded, i.e. updated
    if outputlabel is None:
        outputlabel = epoch_to_string(date_epoch)
    filename = name.lower() + '/' + epoch_to_string(date_epoch) + '.' + get_file_extension(url)
    if os.path.isfile(filename):
        log(outputlabel + ' exists', end=' ', flush=True, quiet=quiet)
        return False
    resp = get_anonymous_session().get(url, stream=True)
    if resp.status_code == 200:
        log(outputlabel, end=' ', flush=True, quiet=quiet)
        os.makedirs(name.lower(), exist_ok=True)
        with open(filename, 'wb') as file:
            resp.raw.decode_content = True
            shutil.copyfileobj(resp.raw, file)
        os.utime(filename, (datetime.datetime.now().timestamp(), date_epoch))
        return True
    else:
        raise ConnectionException("File \'" + url + "\' could not be downloaded.")

def save_caption(name, date_epoch, caption, quiet=False):
    filename = name.lower() + '/' + epoch_to_string(date_epoch) + '.txt'
    pcaption = caption.replace('\n', ' ').strip()
    caption = caption.encode("UTF-8")
    if os.name in ['nt', 'ce'] and not WINUNICODE:
        output = str()
    else:
        output = '[' + ((pcaption[:26]+"…") if len(pcaption)>28 else pcaption) + ']'
    if os.path.isfile(filename):
        with open(filename, 'rb') as file:
            file_caption = file.read()
        if file_caption.replace(b'\r\n', b'\n') == caption.replace(b'\r\n', b'\n'):
            output = output + ' unchanged'
            log(output, end=' ', flush=True, quiet=quiet)
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
            output = output + ' updated'
    log(output, end=' ', flush=True, quiet=quiet)
    os.makedirs(name.lower(), exist_ok=True)
    with open(filename, 'wb') as text_file:
        shutil.copyfileobj(BytesIO(caption), text_file)
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
        raise ConnectionException("URL \'" + url + "\' could not be processed.")
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
        raise ConnectionException("File \'" + url + "\' could not be downloaded.")

def get_default_session_filename(username):
    dirname = tempfile.gettempdir() + "/" + ".instaloader-" + getpass.getuser()
    filename = dirname + "/" + "session-" + username
    return filename

def save_session(session, username, filename=None, quiet=False):
    if filename is None:
        filename = get_default_session_filename(username)
    dirname = os.path.dirname(filename)
    if not os.path.exists(dirname):
        os.makedirs(dirname)
        os.chmod(dirname, 0o700)
    with open(filename, 'wb') as sessionfile:
        os.chmod(filename, 0o600)
        pickle.dump(requests.utils.dict_from_cookiejar(session.cookies), sessionfile)
        log("Saved session to %s." % filename, quiet=quiet)

def load_session(username, filename=None, quiet=False):
    if filename is None:
        filename = get_default_session_filename(username)
    try:
        with open(filename, 'rb') as sessionfile:
            session = requests.Session()
            session.cookies = requests.utils.cookiejar_from_dict(pickle.load(sessionfile))
            session.headers.update(default_http_header())
            session.headers.update({'X-CSRFToken':session.cookies.get_dict()['csrftoken']})
            log("Loaded session from %s." % filename, quiet=quiet)
            return session
    except FileNotFoundError:
        pass

def copy_session(session):
    new = requests.Session()
    new.cookies = \
            requests.utils.cookiejar_from_dict(requests.utils.dict_from_cookiejar(session.cookies))
    new.headers = session.headers
    return new

def test_login(session):
    if session is None:
        return
    data = get_json(str(), session)
    if data['config']['viewer'] is None:
        return
    time.sleep(4 * random.random() + 1)
    return data['config']['viewer']['username']

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
        if user == test_login(session):
            return session
        else:
            raise BadCredentialsException('Login error! Check your credentials!')
    else:
        raise ConnectionException('Login error! Connection error!')

def check_id(profile, session, json_data, quiet):
    profile_exists = len(json_data["entry_data"]) > 0 and "ProfilePage" in json_data["entry_data"]
    is_logged_in = json_data["config"]["viewer"] is not None
    if os.path.isfile(profile + "/id"):
        with open(profile + "/id", 'rb') as id_file:
            profile_id = int(id_file.read())
        if (not profile_exists) or \
            (profile_id != int(json_data['entry_data']['ProfilePage'][0]['user']['id'])):
            if is_logged_in:
                newname = get_username_by_id(session, profile_id)
                log("Profile {0} has changed its name to {1}.".format(profile, newname),
                    quiet=quiet)
                os.rename(profile, newname)
                return newname
            if profile_exists:
                raise ProfileNotExistsException("Profile {0} does not match the stored "
                                                "unique ID {1}.".format(profile, profile_id))
            raise ProfileNotExistsException("Profile {0} does not exist. Please login to "
                                            "update profile name. Unique ID: {1}."
                                            .format(profile, profile_id))
        return profile
    if profile_exists:
        os.makedirs(profile.lower(), exist_ok=True)
        with open(profile + "/id", 'w') as text_file:
            profile_id = json_data['entry_data']['ProfilePage'][0]['user']['id']
            text_file.write(profile_id)
            log("Stored ID {0} for profile {1}.".format(profile_id, profile), quiet=quiet)
        return profile
    raise ProfileNotExistsException("Profile {0} does not exist.".format(profile))

def download(name, session, profile_pic_only=False, download_videos=True,
        fast_update=False, sleep_min_max=[0.25,2], quiet=False):
    """Download one profile"""
    # pylint:disable=too-many-arguments,too-many-branches
    # Get profile main page json
    data = get_json(name, session)
    # check if profile does exist or name has changed since last download
    # and update name and json data if necessary
    name_updated = check_id(name, session, data, quiet=quiet)
    if name_updated != name:
        name = name_updated
        data = get_json(name, session)
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
            raise PrivateProfileNotFollowedException("Profile %s: private but not followed." % name)
    else:
        if data["config"]["viewer"] is not None:
            log("profile %s could also be downloaded anonymously." % name, quiet=quiet)
    if ("nodes" not in data["entry_data"]["ProfilePage"][0]["user"]["media"] or
            len(data["entry_data"]["ProfilePage"][0]["user"]["media"]["nodes"]) == 0) \
                    and not profile_pic_only:
        raise ProfileHasNoPicsException("Profile %s: no pics found." % name)
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
            else:
                log("<no caption>", end=' ', flush=True, quiet=quiet)
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

def download_profiles(profilelist, username=None, password=None, sessionfile=None,
        profile_pic_only=False, download_videos=True, fast_update=False,
        sleep_min_max=[0.25,2], quiet=False):
    """Download set of profiles and handle sessions"""
    # pylint:disable=too-many-arguments,too-many-branches,too-many-locals
    # Login, if desired
    if username is not None:
        session = load_session(username, sessionfile, quiet=quiet)
        if username != test_login(session):
            session = get_logged_in_session(username, password, quiet)
        log("Logged in as %s." % username, quiet=quiet)
    else:
        session = get_anonymous_session()
    # Try block for KeyboardInterrupt (save session on ^C)
    failedtargets = []
    targets = set()
    try:
        # Generate set of targets
        for pentry in profilelist:
            if pentry[0] == '@':
                log("Retrieving followees of %s..." % pentry[1:], quiet=quiet)
                followees = get_followees(pentry[1:], session)
                targets.update([followee['username'] for followee in followees])
            else:
                targets.add(pentry)
        if len(targets) == 0:
            log("No profiles to download given.", quiet=quiet)
        elif len(targets) > 1:
            log("Downloading %i profiles..." % len(targets), quiet=quiet)
        # Iterate through targets list and download them
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
        print("Errors occured (see above) while downloading profiles: %s." %
                ", ".join(failedtargets), file=sys.stderr)
    # Save session if it is useful
    if username is not None:
        save_session(session, username, sessionfile, quiet=quiet)

def main():
    parser = ArgumentParser(description='Simple downloader to fetch all Instagram pics and '\
                                        'captions from a given profile')
    parser.add_argument('profile', nargs='*',
            help='Name of profile to download, or @<profile> to download all followees of '\
                    '<profile>')
    parser.add_argument('--version', action='version',
                        version='1.0.1')
    parser.add_argument('-l', '--login', metavar='YOUR-USERNAME',
            help='Login name for your Instagram account. Not needed to download public '\
                    'profiles, but if you want to download private profiles or all followees of '\
                    'some profile, you have to specify a username used to login.')
    parser.add_argument('-p', '--password', metavar='YOUR-PASSWORD',
            help='Password for your Instagram account. If --login is given and there is '\
                    'not yet a valid session file, you\'ll be prompted for your password if '\
                    '--password is not given. Specifying this option without --login has no '\
                    'effect.')
    parser.add_argument('-f', '--sessionfile',
            help='File to store session key, defaults to '+ \
            get_default_session_filename("<login_name>"))
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
        download_profiles(args.profile, args.login, args.password, args.sessionfile,
                args.profile_pic_only, not args.skip_videos, args.fast_update,
                [0,0] if args.no_sleep else [0.25,2], args.quiet)
    except InstaloaderException as err:
        raise SystemExit("Fatal error: %s" % err)

if __name__ == "__main__":
    main()
