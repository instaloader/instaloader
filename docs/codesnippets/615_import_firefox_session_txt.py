#!/usr/local/bin/python3

import http.cookiejar
from argparse import ArgumentParser

# This script attempts to load a cookies.txt file,
# login to instagram and write the instaloader session file.
# Try this method if you have trouble logging in using instaloader.

try:
    from instaloader import ConnectionException, Instaloader
except ModuleNotFoundError:
    raise SystemExit("Instaloader not found.\n  pip install [--user] instaloader")

def import_session(cookiefile, sessionfile):
    print("Using cookies from {}.".format(cookiefile))
    cj = http.cookiejar.MozillaCookieJar()
    cj.load(cookiefile, ignore_discard=True, ignore_expires=True)
    instaloader = Instaloader(max_connection_attempts=1)
    instaloader.context._session.cookies.update(cj)
    username = instaloader.test_login()
    if not username:
        raise SystemExit("Not logged in. Are you logged in successfully in Firefox?")
    print("Imported session cookie for {}.".format(username))
    instaloader.context.username = username
    instaloader.save_session_to_file(sessionfile)

if __name__ == "__main__":
    p = ArgumentParser()
    p.add_argument("-c", "--cookiefile")
    p.add_argument("-f", "--sessionfile")
    args = p.parse_args()
    try:
        import_session(args.cookiefile, args.sessionfile)
    except (ConnectionException, OperationalError) as e:
        raise SystemExit("Cookie import failed: {}".format(e))
