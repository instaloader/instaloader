import instaloader

L = instaloader.Instaloader()

USER = "your_account"
PROFILE = USER

# Load session previously saved with `instaloader -l USERNAME`:
L.load_session_from_file(USER)

profile = instaloader.Profile.from_username(L.context, PROFILE)

likes = set()
print("Fetching likes of all posts of profile {}.".format(profile.username))
for post in profile.get_posts():
    print(post)
    likes = likes | set(post.get_likes())

print("Fetching followers of profile {}.".format(profile.username))
followers = set(profile.get_followers())

ghosts = followers - likes

print("Storing ghosts into file.")
with open("inactive-users.txt", 'w') as f:
    for ghost in ghosts:
        print(ghost.username, file=f)
