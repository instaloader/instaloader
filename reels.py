import instaloader
import time
import os
import argparse

user_agent1 = 'YOUR_USERAGENT'
filename_pattern1 = r'{profile}{date_utc}{filename}'
login = 'YOUR_USERNAME'

L = instaloader.Instaloader(user_agent=user_agent1, filename_pattern=filename_pattern1)
parser = argparse.ArgumentParser()
parser.add_argument('reel')
args = parser.parse_args()

L.load_session_from_file(login)

post = instaloader.Post.from_shortcode(L.context, args.reel)
L.download_post(post, target=args.reel)
