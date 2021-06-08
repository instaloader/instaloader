# This will automatically import cookies and create a session file
# Works on all browsers that support EditThisCookie extension (http://www.editthiscookie.com/)
#
# Instructions:
#     1. Install EditThisCookie extension on your supported browser
#     2. Login to your Instagram account on that browser
#     3. Export the cookies using the EditThisCookie extension (will copy them to the clipboard)
#     4. Paste the exported cookies to a file (cookies.txt is the default filename)
#     5. Use this script to create a valid session file

from argparse import ArgumentParser
from glob import glob
from os.path import expanduser
from platform import system
import json

try:
    from instaloader import ConnectionException, Instaloader
except ModuleNotFoundError:
    raise SystemExit("Instaloader not found.\n  pip install [--user] instaloader")


def get_cookiefile():
    default_cookiefile = "cookies.txt"
    cookiefiles = glob(expanduser(default_cookiefile))
    if not cookiefiles:
        raise SystemExit("No exported cookies file found. Use -c COOKIEFILE.")
    return cookiefiles[0]


def import_session(cookiefile, sessionfile):
    print("Using cookies from {}.".format(cookiefile))

    with open(cookiefile, 'r') as f:
        data = json.load(f)

    cookie_data = {}
    for x in data:
        cookie_data[str(x["name"])] = str(x["value"])    
        
    instaloader = Instaloader(max_connection_attempts=1)
    instaloader.context._session.cookies.update(cookie_data)
    username = instaloader.test_login()
    if not username:
        raise SystemExit("Not logged in. Have you correctly exported and created your cookies file?")
    print("Imported session cookie for {}.".format(username))
    instaloader.context.username = username
    instaloader.save_session_to_file(sessionfile)


if __name__ == "__main__":
    p = ArgumentParser()
    p.add_argument("-c", "--cookiefile")
    p.add_argument("-f", "--sessionfile")
    args = p.parse_args()
    try:
        import_session(args.cookiefile or get_cookiefile(), args.sessionfile)
    except (ConnectionException, OperationalError) as e:
        raise SystemExit("Cookie import failed: {}".format(e))
