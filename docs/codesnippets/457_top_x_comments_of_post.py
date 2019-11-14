from itertools import islice
from math import ceil

from instaloader import Instaloader, Post

SHORTCODE = '...'        # post to download from
X_percentage = 10    # percentage of comment that should be downloaded

L = Instaloader()

post = Post.from_shortcode(L.context, SHORTCODE)
comments_sorted_by_likes = sorted(post.get_comments(),key=lambda p: p.likes_count, reverse=True)

for comment in islice(comments_sorted_by_likes, ceil(post.comments * X_percentage / 100)):
    print(comment.text)
