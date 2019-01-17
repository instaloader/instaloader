from glob import glob
from os.path import expanduser
from sqlite3 import connect

from instaloader import ConnectionException, Instaloader

# FIREFOXCOOKIEFILE = "/home/alex/.mozilla/firefox/l96w6b90.default/cookies.sqlite"
FIREFOXCOOKIEFILE = glob(expanduser("~/.mozilla/firefox/*.default/cookies.sqlite"))[0]

instaloader = Instaloader(max_connection_attempts=1)
instaloader.context._session.cookies.update(connect(FIREFOXCOOKIEFILE)
                                            .execute("SELECT name, value FROM moz_cookies "
                                                     "WHERE baseDomain='instagram.com'"))

try:
    username = instaloader.test_login()
    if not username:
        raise ConnectionException()
except ConnectionException:
    raise SystemExit("Cookie import failed. Are you logged in successfully in Firefox?")

instaloader.context.username = username
instaloader.save_session_to_file()
