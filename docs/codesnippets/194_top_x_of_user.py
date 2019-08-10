from itertools import islice
from math import ceil

from instaloader import Instaloader, Profile

PROFILE = ...        # profile to download from
X_percentage = 10    # percentage of posts that should be downloaded

L = Instaloader()

profile = Profile.from_username(L.context, PROFILE)
posts_sorted_by_likes = sorted(profile.get_posts(),
                               key=lambda p: p.likes + p.comments,
                               reverse=True)

for post in islice(posts_sorted_by_likes, ceil(profile.mediacount * X_percentage / 100)):
    L.download_post(post, PROFILE)
