from glob import glob
from sys import argv
from os import chdir

from instaloader import Instaloader, Post, Profile, load_structure_from_file

# Instaloader instantiation - you may pass additional arguments to the constructor here
L = Instaloader()

# If desired, load session previously saved with `instaloader -l USERNAME`:
#L.load_session_from_file(USERNAME)

try:
    TARGET = argv[1]
except IndexError:
    raise SystemExit("Pass profile name as argument!")

# Obtain set of posts that are on hard disk
chdir(TARGET)
offline_posts = set(filter(lambda s: isinstance(s, Post),
                           (load_structure_from_file(L.context, file)
                            for file in (glob('*.json.xz') + glob('*.json')))))

# Obtain set of posts that are currently online
post_iterator = Profile.from_username(L.context, TARGET).get_posts()
online_posts = set(post_iterator)

if online_posts - offline_posts:
    print("Not yet downloaded posts:")
    print(" ".join(str(p) for p in (online_posts - offline_posts)))

if offline_posts - online_posts:
    print("Deleted posts:")
    print(" ".join(str(p) for p in (offline_posts - online_posts)))
