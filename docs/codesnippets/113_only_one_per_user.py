import instaloader

L = instaloader.Instaloader()

posts = instaloader.Hashtag.from_name(L.context, 'urbanphotography').get_posts()

users = set()

for post in posts:
    if not post.owner_profile in users:
        L.download_post(post, '#urbanphotography')
        users.add(post.owner_profile)
    else:
        print(f"{post} from {post.owner_profile} skipped.")
