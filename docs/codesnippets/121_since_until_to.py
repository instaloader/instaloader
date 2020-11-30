from datetime import timedelta
import instaloader

L = instaloader.Instaloader()
profile = instaloader.Profile.from_username(L.context, "instagram")
posts = profile.get_posts()

for post in posts.since(ago=timedelta(days=3)):
    L.download_post(post, "instagram")
