#!/usr/bin/env python3

import requests, re, json, datetime, shutil, os

class DownloaderException(Exception):
    pass

def get_json(name, id = 0):
    r = requests.get('http://www.instagram.com/'+name, \
        params={'max_id': id})
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
        print(outputlabel + ' exists', end='  ', flush=True)
        return False
    r = requests.get(url, stream=True)
    if r.status_code == 200:
        print(outputlabel, end='  ', flush=True)
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
            print('txt unchanged', end=' ', flush=True)
            return None
        else:
            def get_filename(index):
                return filename if index==0 else (filename[:-4] + '_old_' + \
                        (str(0) if index<10 else str()) + str(index) + filename[-4:])
            i = 0
            while os.path.isfile(get_filename(i)):
                i = i + 1
            for index in range(i, 0, -1):
                os.rename(get_filename(index-1), get_filename(index));
            print('txt updated', end=' ', flush=True)
    print('txt', end=' ', flush=True)
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
        print(filename + ' already exists')
        return None
    m = re.search('http.*://.*instagram\.com/[^/]+/.', url)
    index = len(m.group(0))-1
    offset = 8 if m.group(0)[-1:] == 's' else 0
    url = url[:index] + 's2048x2048' + ('/' if offset == 0 else str()) + url[index+offset:]
    r = requests.get(url, stream=True)
    if r.status_code == 200:
        print(filename)
        os.makedirs(name.lower(), exist_ok=True)
        with open(filename, 'wb') as f:
            r.raw.decode_content = True
            shutil.copyfileobj(r.raw, f)
        os.utime(filename, (datetime.datetime.now().timestamp(), date_object.timestamp()))
    else:
        raise DownloaderException("file \'" + url + "\' could not be downloaded")

def download(name, ProfilePicOnly = False, DownloadVideos = True, FastUpdate = False):
    data = get_json(name)
    totalcount = data["entry_data"]["ProfilePage"][0]["user"]["media"]["count"]
    if len(data["entry_data"]) == 0:
        raise DownloaderException("user does not exist")
    else:
        download_profilepic(name, data["entry_data"]["ProfilePage"][0]["user"]["profile_pic_url"])
        if len(data["entry_data"]["ProfilePage"][0]["user"]["media"]["nodes"]) == 0 \
                and not ProfilePicOnly:
            raise DownloaderException("no pics found")
    if not ProfilePicOnly:
        count = 1
        while not get_last_id(data) is None:
            for node in data["entry_data"]["ProfilePage"][0]["user"]["media"]["nodes"]:
                print("[%3i/%3i] " % (count, totalcount), end="", flush=True)
                count = count + 1
                downloaded = download_pic(name, node["display_src"], node["date"])
                if "caption" in node:
                    saveCaption(name, node["date"], node["caption"])
                if node["is_video"] and DownloadVideos:
                    video_data = get_json('p/' + node["code"])
                    download_pic(name, \
                            video_data['entry_data']['PostPage'][0]['media']['video_url'], \
                            node["date"], 'mp4')
                print()
                if FastUpdate and not downloaded:
                    return
            data = get_json(name, get_last_id(data))

if __name__ == "__main__":
    from argparse import ArgumentParser
    parser = ArgumentParser(description='Simple downloader to fetch all Instagram pics and '\
                                        'captions from a given public profile')
    parser.add_argument('name', help='Name of profile to download')
    parser.add_argument('-P', '--profile-pic-only', action='store_true',
            help='Only download profile picture')
    parser.add_argument('-V', '--skip-videos', action='store_true',
            help='Do not download videos')
    parser.add_argument('-F', '--fast-update', action='store_true',
            help='Abort at encounter of first already-downloaded picture')
    args = parser.parse_args()
    download(args.name, args.profile_pic_only, not args.skip_videos, args.fast_update)
