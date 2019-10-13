from datetime import datetime
from itertools import dropwhile, takewhile

import instaloader

L = instaloader.Instaloader()

posts = L.get_hashtag_posts('urbanphotography')
# or
# posts = instaloader.Profile.from_username(L.context, PROFILE).get_posts()

SINCE = datetime(2015, 5, 1)
UNTIL = datetime(2015, 3, 1)

for post in takewhile(lambda p: p.date > UNTIL, dropwhile(lambda p: p.date > SINCE, posts)):
    print(post.date)
    L.download_post(post, '#urbanphotography')
