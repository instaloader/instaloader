# https://n8henrie.com/2013/11/use-chromes-cookies-for-easier-downloading-with-python-requests/

from argparse import ArgumentParser
from glob import glob
from os.path import expanduser
from platform import system
from sqlite3 import OperationalError, connect
import win32crypt
import requests
import json
import base64
from Crypto.Cipher import AES

try:
	from instaloader import ConnectionException, Instaloader
except ModuleNotFoundError:
	raise SystemExit("Instaloader not found.\n  pip install [--user] instaloader")


def get_cryptokey():	
	default_cryptokeylocation = {
		"Windows": "~/AppData/Local/Google/Chrome/User Data/Local State",
		"Darwin": "~/Library/Application Support/Google/Chrome/Default/Cookies",
	}.get(system(), "~/.config/chromium/Default/Cookies")
	print("Attempting to retrieve cryptographic key.")
	cryptokeylocation = glob(expanduser(default_cryptokeylocation))[0]
	try:
		with open(cryptokeylocation, 'r') as ls:
			cryptokey = json.loads(ls.read())['os_crypt']['encrypted_key']
	except FileNotFoundError:
			raise SystemExit("Failed to find Chrome's Local State")	
	cryptokey = base64.b64decode(cryptokey)[5:]
	cryptokey = win32crypt.CryptUnprotectData(cryptokey, None, None, None, 0)[1]
	return cryptokey


def get_cookiefile():
	default_cookiefile = {
		"Windows": "~/AppData/Local/Google/Chrome/User Data/Default/Network/cookies",
		"Darwin": "~/Library/Application Support/Google/Chrome/Default/Cookies",
	}.get(system(), "~/.config/chromium/Default/Cookies")
	cookiefiles = glob(expanduser(default_cookiefile))
	if not cookiefiles:
		raise SystemExit("No Chrome cookies file found. Use -c COOKIEFILE.")
	return cookiefiles[0]


def get_cookies(curr):
	cookie_data = {}
	cookie_names = ["csrftoken", "datr", "ds_user_id", "ig_did", "ig_pr", "ig_vw", "mid", "s_network", "sessionid", "shbid", "shbts"]
	decryption_key = get_cryptokey()
	if not decryption_key:
		raise SystemExit("Failed to retrieve decryption key from Chrome's Local State")	
	for name, encrypted_value in curr.fetchall():
		cipher = AES.new(decryption_key, AES.MODE_GCM, nonce=encrypted_value[3:15])
		decrypted_value = cipher.decrypt(encrypted_value[15:])[:-16].decode()
		if name in cookie_names:
			cookie_data[name] = decrypted_value		
	return cookie_data

def import_session(cookiefile, sessionfile):
	print("Using cookies from {}.".format(cookiefile))
	conn = connect(f"file:{cookiefile}?immutable=1", uri=True)
	try:
		curr = conn.execute(
			"SELECT name, encrypted_value FROM cookies WHERE host_key LIKE '%instagram.com'"			
		)
	except OperationalError:
		curr = conn.execute(
			"SELECT name, encrypted_value FROM cookies WHERE host_key='instagram.com'"
		)
	cookie_data = get_cookies(curr)
	instaloader = Instaloader(max_connection_attempts=1)
	instaloader.context._session.cookies = requests.utils.cookiejar_from_dict(cookie_data)
	username = instaloader.test_login()
	if not username:
		raise SystemExit("Not logged in. Are you logged in successfully in Chrome?")
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