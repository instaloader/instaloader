#!/usr/bin/env python3

import re, json, datetime, shutil, os, time, random, sys, pickle, getpass
from io import BytesIO
from argparse import ArgumentParser
import requests

DEFAULTSESSIONFILE = "/tmp/.instaloadersession"

class DownloaderException(Exception):
    pass

class ProfileNotExistsException(DownloaderException):
    pass

class ProfileHasNoPicsException(DownloaderException):
    pass

class PrivateProfileNotFollowedException(DownloaderException):
    pass

class LoginRequiredException(DownloaderException):
    pass

def log(*msg, sep='', end='\n', flush=False, quiet=False):
    if not quiet:
        print(*msg, sep=sep, end=end, flush=flush)

def get_json(name, max_id = 0, session=None, sleep_min_max=[1,5]):
    if session is None:
        session = get_session(None, None, True)
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
    resp = get_session(None, None, True).get(url, stream=True)
    if resp.status_code == 200:
        log(outputlabel, end='  ', flush=True, quiet=quiet)
        os.makedirs(name.lower(), exist_ok=True)
        with open(filename, 'wb') as file:
            resp.raw.decode_content = True
            shutil.copyfileobj(resp.raw, file)
        os.utime(filename, (datetime.datetime.now().timestamp(), date_epoch))
        return True
    else:
        raise DownloaderException("file \'" + url + "\' could not be downloaded")

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
        raise DownloaderException("url \'" + url + "\' could not be processed")
    index = len(match.group(0))-1
    offset = 8 if match.group(0)[-1:] == 's' else 0
    url = url[:index] + 's2048x2048' + ('/' if offset == 0 else str()) + url[index+offset:]
    resp = get_session(None, None, True).get(url, stream=True)
    if resp.status_code == 200:
        log(filename, quiet=quiet)
        os.makedirs(name.lower(), exist_ok=True)
        with open(filename, 'wb') as file:
            resp.raw.decode_content = True
            shutil.copyfileobj(resp.raw, file)
        os.utime(filename, (datetime.datetime.now().timestamp(), date_object.timestamp()))
    else:
        raise DownloaderException("file \'" + url + "\' could not be downloaded")

def save_object(obj, filename):
    if filename is None:
        filename = DEFAULTSESSIONFILE
    with open(filename, 'wb') as file:
        os.chmod(filename, 0o600)
        shutil.copyfileobj(BytesIO(pickle.dumps(obj, -1)), file)

def load_object(filename):
    if filename is None:
        filename = DEFAULTSESSIONFILE
    if os.path.isfile(filename):
        with open(filename, 'rb') as sessionfile:
            obj = pickle.load(sessionfile)
        return obj
    else:
        return None

def test_login(user, session):
    if user is None or session is None:
        return False
    resp = session.get('https://www.instagram.com/')
    time.sleep(4 * random.random() + 1)
    return resp.text.find(user.lower()) != -1

def get_session(user, passwd, empty_session_only=False, session=None):
    def instaheader():
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
    if session is None:
        session = requests.Session()
        session.cookies.update({'sessionid' : '', 'mid' : '', 'ig_pr' : '1', \
                                     'ig_vw' : '1920', 'csrftoken' : '', \
                                           's_network' : '', 'ds_user_id' : ''})
    session.headers.update(instaheader())
    if empty_session_only:
        return session
    resp = session.get('https://www.instagram.com/')
    session.headers.update({'X-CSRFToken':resp.cookies['csrftoken']})
    time.sleep(9 * random.random() + 3)
    login = session.post('https://www.instagram.com/accounts/login/ajax/', \
            data={'password':passwd,'username':user}, allow_redirects=True)
    session.headers.update({'X-CSRFToken':login.cookies['csrftoken']})
    time.sleep(5 * random.random())
    if login.status_code == 200:
        if test_login(user, session):
            return session, True
        else:
            print('Login error! Check your credentials!', file=sys.stderr)
            return session, False
    else:
        print('Login error! Connection error!', file=sys.stderr)
        return session, False

def download(name, username = None, password = None, sessionfile = None, \
    profile_pic_only = False, download_videos = True, fast_update = False, \
    sleep_min_max=[0.25,2], quiet=False):
    # pylint:disable=too-many-arguments,too-many-locals,too-many-nested-blocks,too-many-branches
    # We are aware that this function has many arguments, many local variables, many nested blocks
    # and many branches. But we don't care.
    session = load_object(sessionfile)
    data = get_json(name, session=session)
    if len(data["entry_data"]) == 0 or "ProfilePage" not in data["entry_data"]:
        raise ProfileNotExistsException("user %s does not exist" % name)
    else:
        download_profilepic(name, data["entry_data"]["ProfilePage"][0]["user"]["profile_pic_url"],
                quiet=quiet)
        time.sleep(abs(sleep_min_max[1]-sleep_min_max[0])*random.random()+abs(sleep_min_max[0]))
        if not profile_pic_only and data["entry_data"]["ProfilePage"][0]["user"]["is_private"]:
            if not test_login(username, session):
                if username is None or password is None:
                    if quiet:
                        raise LoginRequiredException("user %s requires login" % name)
                    while True:
                        if username is None:
                            username = input('Enter your Instagram username to login: ')
                        if password is None:
                            password = getpass.getpass(
                                prompt='Enter your corresponding Instagram password: ')
                        session, status = get_session(username, password, session=session)
                        if status:
                            break
                        username = None
                        password = None
                else:
                    session, status = get_session(username, password, session=session)
                    if not status:
                        raise DownloaderException("aborting due to login error")
                data = get_json(name, session=session)
            if not data["entry_data"]["ProfilePage"][0]["user"]["followed_by_viewer"]:
                raise PrivateProfileNotFollowedException("user %s: private but not followed" % name)
        if ("nodes" not in data["entry_data"]["ProfilePage"][0]["user"]["media"] \
            or len(data["entry_data"]["ProfilePage"][0]["user"]["media"]["nodes"]) == 0) \
                and not profile_pic_only:
            raise ProfileHasNoPicsException("user %s: no pics found" % name)
    totalcount = data["entry_data"]["ProfilePage"][0]["user"]["media"]["count"]
    if not profile_pic_only:
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
                    video_data = get_json('p/' + node["code"], session=session)
                    download_pic(name, \
                            video_data['entry_data']['PostPage'][0]['media']['video_url'], \
                            node["date"], 'mp4', quiet=quiet)
                log(quiet=quiet)
                if fast_update and not downloaded:
                    if test_login(username, session):
                        save_object(session, sessionfile)
                    return username
            data = get_json(name, get_last_id(data), session)
            time.sleep(abs(sleep_min_max[1]-sleep_min_max[0])*random.random()+abs(sleep_min_max[0]))
    if test_login(username, session):
        save_object(session, sessionfile)
    return username

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
    username = args.login
    failedtargets = []
    for target in args.targets:
        try:
            username = download(target, username, args.password, args.sessionfile,
                     args.profile_pic_only, not args.skip_videos, args.fast_update,
                     [0,0] if args.no_sleep else [0.25,2], args.quiet)
        except (ProfileNotExistsException, ProfileHasNoPicsException,
                PrivateProfileNotFollowedException, LoginRequiredException) as err:
            failedtargets.append(target)
            print("%s" % err, file=sys.stderr)
    if len(args.targets) > 1 and len(failedtargets) > 0:
        print("Errors occured (see above) while downloading profiles: %s" %
                ", ".join(failedtargets), file=sys.stderr)

if __name__ == "__main__":
    main()
