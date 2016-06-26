#!/usr/bin/env python3

import re, json, datetime, shutil, os, time, random, sys, pickle, getpass
from io import BytesIO
from argparse import ArgumentParser
import requests

class DownloaderException(Exception):
    pass

quiet = False

def log(*msg, sep='', end='\n', flush=False):
    if not quiet:
        print(*msg, sep=sep, end=end, flush=flush)

def get_json(name, max_id = 0, session=None, SleepMinMax=[1,5]):
    if session is None:
        session = get_session(None, None, True)
    r = session.get('http://www.instagram.com/'+name, \
        params={'max_id': max_id})
    time.sleep(abs(SleepMinMax[1]-SleepMinMax[0])*random.random()+SleepMinMax[0])
    m = re.search('window\._sharedData = .*<', r.text)
    if m is None:
        return None
    else:
        return json.loads(m.group(0)[21:-2])

def get_last_id(data):
    if len(data["entry_data"]) == 0 or \
        len(data["entry_data"]["ProfilePage"][0]["user"]["media"]["nodes"]) == 0:
        return None
    else:
        data = data["entry_data"]["ProfilePage"][0]["user"]["media"]["nodes"]
        return int(data[len(data)-1]["id"])

def epochToString(epoch):
    return datetime.datetime.fromtimestamp(epoch).strftime('%Y-%m-%d_%H-%M-%S')

def get_fileExtension(url):
    m = re.search('\.[a-z]*\?', url)
    if m is None:
        return url[-3:]
    else:
        return m.group(0)[1:-1]

def download_pic(name, url, date_epoch, outputlabel=None):
    # Returns true, if file was actually downloaded, i.e. updated
    if outputlabel is None:
        outputlabel = epochToString(date_epoch)
    filename = name.lower() + '/' + epochToString(date_epoch) + '.' + get_fileExtension(url)
    if os.path.isfile(filename):
        log(outputlabel + ' exists', end='  ', flush=True)
        return False
    r = get_session(None, None, True).get(url, stream=True)
    if r.status_code == 200:
        log(outputlabel, end='  ', flush=True)
        os.makedirs(name.lower(), exist_ok=True)
        with open(filename, 'wb') as f:
            r.raw.decode_content = True
            shutil.copyfileobj(r.raw, f)
        os.utime(filename, (datetime.datetime.now().timestamp(), date_epoch))
        return True
    else:
        raise DownloaderException("file \'" + url + "\' could not be downloaded")

def saveCaption(name, date_epoch, caption):
    filename = name.lower() + '/' + epochToString(date_epoch) + '.txt'
    if os.path.isfile(filename):
        with open(filename, 'r') as f:
            fileCaption = f.read()
        if fileCaption == caption:
            log('txt unchanged', end=' ', flush=True)
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
            log('txt updated', end=' ', flush=True)
    log('txt', end=' ', flush=True)
    os.makedirs(name.lower(), exist_ok=True)
    with open(filename, 'w') as text_file:
        text_file.write(caption)
    os.utime(filename, (datetime.datetime.now().timestamp(), date_epoch))

def download_profilepic(name, url):
    date_object = datetime.datetime.strptime(requests.head(url).headers["Last-Modified"], \
        '%a, %d %b %Y %H:%M:%S GMT')
    filename = name.lower() + '/' + epochToString(date_object.timestamp()) + \
        '_UTC_profile_pic.' + url[-3:]
    if os.path.isfile(filename):
        log(filename + ' already exists')
        return None
    m = re.search('http.*://.*instagram.*[^/]*\.(com|net)/[^/]+/.', url)
    if m is None:
        raise DownloaderException("url \'" + url + "\' could not be processed")
    index = len(m.group(0))-1
    offset = 8 if m.group(0)[-1:] == 's' else 0
    url = url[:index] + 's2048x2048' + ('/' if offset == 0 else str()) + url[index+offset:]
    r = get_session(None, None, True).get(url, stream=True)
    if r.status_code == 200:
        log(filename)
        os.makedirs(name.lower(), exist_ok=True)
        with open(filename, 'wb') as f:
            r.raw.decode_content = True
            shutil.copyfileobj(r.raw, f)
        os.utime(filename, (datetime.datetime.now().timestamp(), date_object.timestamp()))
    else:
        raise DownloaderException("file \'" + url + "\' could not be downloaded")

def save_object(obj, filename):
    if filename is None:
        filename = '/tmp/instaloader.session'
    with open(filename, 'wb') as f:
        shutil.copyfileobj(BytesIO(pickle.dumps(obj, -1)), f)

def load_object(filename):
    if filename is None:
        filename = '/tmp/instaloader.session'
    if os.path.isfile(filename):
        with open(filename, 'rb') as f:
            obj = pickle.load(f)
        return obj
    else:
        return None

def test_login(user, session):
    if user is None or session is None:
        return False
    r = session.get('https://www.instagram.com/')
    time.sleep(4 * random.random() + 1)
    return r.text.find(user.lower()) != -1

def get_session(user, passwd, EmptySessionOnly=False, session=None):
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
        if EmptySessionOnly:
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
    if EmptySessionOnly:
        return session
    r = session.get('https://www.instagram.com/')
    session.headers.update({'X-CSRFToken':r.cookies['csrftoken']})
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
    ProfilePicOnly = False, DownloadVideos = True, FastUpdate = False, SleepMinMax=[0.25,2]):
    session = load_object(sessionfile)
    data = get_json(name, session=session)
    if len(data["entry_data"]) == 0:
        raise DownloaderException("user does not exist")
    else:
        download_profilepic(name, data["entry_data"]["ProfilePage"][0]["user"]["profile_pic_url"])
        time.sleep((SleepMinMax[1]-SleepMinMax[0])*random.random()+SleepMinMax[0])
        if not ProfilePicOnly and data["entry_data"]["ProfilePage"][0]["user"]["is_private"]:
            if not test_login(username, session):
                if username is None or password is None:
                    if quiet:
                        raise DownloaderException('Login required, credentials not given, ' \
                                'operating in quiet mode')
                    while True:
                        if username is None:
                            username = input('Enter your Instagram username to login: ')
                        if password is None:
                            password = getpass.getpass(
                                prompt='Enter your corresponding Instagram password: ')
                        session, status = get_session(username, password, session=session)
                        if status:
                            break
                else:
                    session, status = get_session(username, password, session=session)
                    if not status:
                        raise DownloaderException("aborting due to login error")
            data = get_json(name, session=session)
        if (not "nodes" in data["entry_data"]["ProfilePage"][0]["user"]["media"] \
            or len(data["entry_data"]["ProfilePage"][0]["user"]["media"]["nodes"]) == 0) \
                and not ProfilePicOnly:
            raise DownloaderException("no pics found")
    totalcount = data["entry_data"]["ProfilePage"][0]["user"]["media"]["count"]
    if not ProfilePicOnly:
        count = 1
        while not get_last_id(data) is None:
            for node in data["entry_data"]["ProfilePage"][0]["user"]["media"]["nodes"]:
                log("[%3i/%3i] " % (count, totalcount), end="", flush=True)
                count = count + 1
                downloaded = download_pic(name, node["display_src"], node["date"])
                time.sleep(abs(SleepMinMax[1]-SleepMinMax[0])*random.random()+SleepMinMax[0])
                if "caption" in node:
                    saveCaption(name, node["date"], node["caption"])
                if node["is_video"] and DownloadVideos:
                    video_data = get_json('p/' + node["code"], session=session)
                    download_pic(name, \
                            video_data['entry_data']['PostPage'][0]['media']['video_url'], \
                            node["date"], 'mp4')
                log()
                if FastUpdate and not downloaded:
                    return
            data = get_json(name, get_last_id(data), session)
            time.sleep(abs(SleepMinMax[1]-SleepMinMax[0])*random.random()+SleepMinMax[0])
    if test_login(username, session):
        save_object(session, sessionfile)

if __name__ == "__main__":
    parser = ArgumentParser(description='Simple downloader to fetch all Instagram pics and '\
                                        'captions from a given profile')
    parser.add_argument('targets', nargs='+', help='Names of profiles to download')
    parser.add_argument('-l', '--login', nargs='?', const=None, metavar='login_name',
            help='Provide login name for your Instagram account')
    parser.add_argument('-p', '--password', nargs='?', const=None,
            help='Provide password for your Instagram account')
    parser.add_argument('-f', '--sessionfile', nargs='?', const=None,
            help='File to store session key, defaults to /tmp/instaloader.session')
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
    quiet = args.quiet
    for target in args.targets:
        download(target, args.login, args.password, args.sessionfile,
                 args.profile_pic_only, not args.skip_videos, args.fast_update,
                 [0,0] if args.no_sleep else [0.25,2])
