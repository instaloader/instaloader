# instaloader

Simple downloader to fetch all Instagram pictures and captions from a given profile.

## Usage

Ensure having [Python](https://www.python.org/) (at least version 3.3) and
[python3-requests](https://pypi.python.org/pypi/requests/) installed.

If you intend to use this tool under Windows, it is highly recommended to first install
[win-unicode-console](https://github.com/Drekin/win-unicode-console).

After having [downloaded instaloader.py](https://github.com/Thammus/instaloader/releases), you
invoke it with
```
./instaloader.py profile [profile ...]
```
where `profile` is the name of a profile you want to download. Instead of only one profile, you may
also specify a list of profiles.

To later update your local copy of that profile, you may run
```
./instaloader.py --fast-update profile [profile ...]
```
When `--fast-update` is given, instaloder terminates when arriving at the first already-downloaded
picture.

Instaloader can also be used to **download private profiles**. To do so, invoke it with
```
./instaloader.py --login=your_username profile [profile ...]
```
When invoked like this, it also **stores the session cookies** in a file in `/tmp`, which will be
reused later when `--login` is given. So you can download private profiles **non-interactively**
when you already have a valid session cookies file.

If you want to **download all followees of a given profile**, call
```
./instaloader.py --login=your_username @profile
```

The `--quiet` option makes it also **suitable as a cron job**.

To get a list of other helpful flags, run `./instaloader.py --help`.

## Usage as library

You may also use parts of instaloader as library to do other interesting things.

For example, to get a list of all followers of a profile as well as their follower count, do
```python
import instaloader

# login
session = instaloader.get_logged_in_session(USERNAME)

# get followees
followees = instaloader.get_followees(PROFILE, session)
for f in followees:
    print("%i\t%s\t%s" % (f['follower_count'], f['username'], f['full_name']))
```

Then, you may download all pictures of all followees with
```python
for f in followees:
    try:
        instaloader.download(f['username'], session)
    except instaloader.NonfatalException:
        pass
```

Each Instagram profile has its own unique ID which stays unmodified even if a user changes his/her
username. To get said ID, given the profile's name, you may call
```python
instaloader.get_id_by_username(PROFILE_NAME)
```

`get_followees()` also returns unique IDs for all loaded followees. To get the current username of a
profile, given this unique ID
`get_username_by_id()` can be used. For example:
```python
instaloader.get_username_by_id(session, followees[0]['id'])
```
