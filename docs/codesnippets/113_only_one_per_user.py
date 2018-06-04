import instaloader

L = instaloader.Instaloader()

posts = L.get_hashtag_posts('milfgarden')

users = set()

for post in posts:
    if not post.owner_profile in users:
        L.download_post(post, '#milfgarden')
        users.add(post.owner_profile)
    else:
        print("{} from {} skipped.".format(post, post.owner_profile))
