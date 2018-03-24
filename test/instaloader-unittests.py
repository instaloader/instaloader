"""Unit Tests for Instaloader"""

import os
import shutil
import tempfile
import unittest

import instaloader

PUBLIC_PROFILE = "Thammus"
PUBLIC_PROFILE_ID = 1700252981
HASHTAG = "kitten"
OWN_USERNAME = "aandergr"
NORMAL_MAX_COUNT = 2
PAGING_MAX_COUNT = 15
PRIVATE_PROFILE = "aandergr"


class TestInstaloader(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        print("Testing in {}".format(self.dir))
        os.chdir(self.dir)
        self.L = instaloader.Instaloader(download_geotags=instaloader.Tristate.always,
                                         download_comments=instaloader.Tristate.always,
                                         save_metadata=instaloader.Tristate.always)
        self.L.raise_all_errors = True

    def tearDown(self):
        self.L.session.close()
        os.chdir('/')
        print("Removing {}".format(self.dir))
        shutil.rmtree(self.dir)

    @unittest.SkipTest
    def test_public_profile_download(self):
        self.L.download_profile(PUBLIC_PROFILE, profile_pic=False, fast_update=True)
        self.L.download_profile(PUBLIC_PROFILE, profile_pic=False, fast_update=True)

    @unittest.SkipTest
    def test_stories_download(self):
        if not self.L.is_logged_in:
            self.L.load_session_from_file(OWN_USERNAME)
        self.L.download_stories()

    @unittest.SkipTest
    def test_private_profile_download(self):
        if not self.L.is_logged_in:
            self.L.load_session_from_file(OWN_USERNAME)
        self.L.download_profile(PRIVATE_PROFILE, download_stories=True)

    def test_profile_pic_download(self):
        self.L.download_profile(PUBLIC_PROFILE, profile_pic_only=True)

    def test_hashtag_download(self):
        self.L.download_hashtag(HASHTAG, NORMAL_MAX_COUNT)

    def test_feed_download(self):
        if not self.L.is_logged_in:
            self.L.load_session_from_file(OWN_USERNAME)
        self.L.download_feed_posts(NORMAL_MAX_COUNT)

    def test_feed_paging(self):
        if not self.L.is_logged_in:
            self.L.load_session_from_file(OWN_USERNAME)
        for count, post in enumerate(self.L.get_feed_posts()):
            print(post)
            if count == PAGING_MAX_COUNT:
                break

    def test_saved_download(self):
        if not self.L.is_logged_in:
            self.L.load_session_from_file(OWN_USERNAME)
        self.L.download_saved_posts(NORMAL_MAX_COUNT)

    def test_saved_paging(self):
        if not self.L.is_logged_in:
            self.L.load_session_from_file(OWN_USERNAME)
        for count, post in enumerate(instaloader.Profile(self.L, OWN_USERNAME).get_saved_posts()):
            print(post)
            if count == PAGING_MAX_COUNT:
                break

    def test_test_login(self):
        if not self.L.is_logged_in:
            self.L.load_session_from_file(OWN_USERNAME)
        self.assertEqual(OWN_USERNAME, self.L.test_login())

    def test_get_followees(self):
        if not self.L.is_logged_in:
            self.L.load_session_from_file(OWN_USERNAME)
        for f in self.L.get_followees(OWN_USERNAME):
            print(f['username'])

    def test_get_followers(self):
        if not self.L.is_logged_in:
            self.L.load_session_from_file(OWN_USERNAME)
        for f in self.L.get_followers(OWN_USERNAME):
            print(f['username'])

    def test_get_username_by_id(self):
        self.assertEqual(PUBLIC_PROFILE.lower(), self.L.get_username_by_id(PUBLIC_PROFILE_ID))

    def test_get_id_by_username(self):
        self.assertEqual(PUBLIC_PROFILE_ID, self.L.get_id_by_username(PUBLIC_PROFILE))

    def test_get_likes(self):
        if not self.L.is_logged_in:
            self.L.load_session_from_file(OWN_USERNAME)
        for post in instaloader.Profile(self.L, OWN_USERNAME).get_posts():
            for like in post.get_likes():
                print(like['username'])
            break

    def test_post_from_mediaid(self):
        for post in instaloader.Profile(self.L, PUBLIC_PROFILE).get_posts():
            post2 = instaloader.Post.from_mediaid(self.L, post.mediaid)
            self.assertEqual(post, post2)
            break


if __name__ == '__main__':
    unittest.main()
