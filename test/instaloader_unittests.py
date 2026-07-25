"""Unit Tests for Instaloader"""

import os
import shutil
import tempfile
import unittest
from itertools import islice
from typing import Optional
from unittest.mock import Mock, patch

import instaloader

PROFILE_WITH_HIGHLIGHTS = 325732271
PUBLIC_PROFILE = "selenagomez"
PUBLIC_PROFILE_ID = 460563723
PUBLIC_PROFILE_WITH_IGTV = "natgeo"
HASHTAG = "kitten"
LOCATION = "362629379"
OWN_USERNAME = "aandergr"
NORMAL_MAX_COUNT = 2
PAGING_MAX_COUNT = 15
PRIVATE_PROFILE = "aandergr"
PRIVATE_PROFILE_ID = 1706625676
EMPTY_PROFILE = "not_public"
EMPTY_PROFILE_ID = 1928659031

ratecontroller: Optional[instaloader.RateController] = None


class TestInstaloaderAnonymously(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        print("Testing in {}".format(self.dir))
        os.chdir(self.dir)
        self.L = instaloader.Instaloader(download_geotags=True,
                                         download_comments=True,
                                         save_metadata=True)
        self.L.context.raise_all_errors = True
        if ratecontroller is not None:
            # pylint:disable=protected-access
            ratecontroller._context = self.L.context
            self.L.context._rate_controller = ratecontroller

    def tearDown(self):
        # pylint:disable=global-statement,protected-access
        global ratecontroller
        ratecontroller = self.L.context._rate_controller
        self.L.close()
        os.chdir('/')
        print("Removing {}".format(self.dir))
        shutil.rmtree(self.dir)

    def post_paging_test(self, iterator):
        previous_post = None
        for post in islice(iterator, PAGING_MAX_COUNT):
            print(post)
            if previous_post:
                self.assertTrue(post.date_utc < previous_post.date_utc)
            previous_post = post

    @unittest.skip('')
    def test_public_profile_download(self):
        profiles = {self.L.check_profile_id(PUBLIC_PROFILE)}
        self.L.download_profiles(profiles, profile_pic=False, fast_update=True, raise_errors=True)
        self.L.download_profiles(profiles, profile_pic=False, fast_update=True, raise_errors=True)

    def test_public_profile_paging(self):
        self.post_paging_test(instaloader.Profile.from_username(self.L.context, PUBLIC_PROFILE).get_posts())

    def test_profile_pic_download(self):
        self.L.download_profiles({self.L.check_profile_id(PUBLIC_PROFILE)}, posts=False, raise_errors=True)

    def test_hashtag_download(self):
        self.L.download_hashtag(HASHTAG, NORMAL_MAX_COUNT)

    def test_hashtag_paging(self):
        for count, post in enumerate(instaloader.Hashtag.from_name(self.L.context, HASHTAG).get_all_posts()):
            print(post)
            if count == PAGING_MAX_COUNT:
                break

    def test_get_id_by_username(self):
        self.assertEqual(PUBLIC_PROFILE_ID,
                         instaloader.Profile.from_username(self.L.context, PUBLIC_PROFILE).userid)

    def test_get_username_by_id_private(self):
        self.assertEqual(PRIVATE_PROFILE.lower(),
                         instaloader.Profile.from_id(self.L.context, PRIVATE_PROFILE_ID).username)

    def test_get_username_by_id_public(self):
        self.assertEqual(PUBLIC_PROFILE.lower(),
                         instaloader.Profile.from_id(self.L.context, PUBLIC_PROFILE_ID).username)

    def test_get_username_by_id_empty(self):
        self.assertEqual(EMPTY_PROFILE.lower(),
                         instaloader.Profile.from_id(self.L.context, EMPTY_PROFILE_ID).username)

    def test_get_username_by_name_empty(self):
        self.assertEqual(EMPTY_PROFILE_ID,
                         instaloader.Profile.from_username(self.L.context, EMPTY_PROFILE).userid)

    def test_post_from_mediaid(self):
        for post in instaloader.Profile.from_username(self.L.context, PUBLIC_PROFILE).get_posts():
            post2 = instaloader.Post.from_mediaid(self.L.context, post.mediaid)
            self.assertEqual(post, post2)
            break

    def test_public_profile_tagged_paging(self):
        for post in islice(instaloader.Profile.from_username(self.L.context, PUBLIC_PROFILE).get_tagged_posts(),
                           PAGING_MAX_COUNT):
            print(post)

    def test_public_profile_igtv(self):
        for post in islice(instaloader.Profile.from_username(self.L.context, PUBLIC_PROFILE_WITH_IGTV).get_igtv_posts(),
                           PAGING_MAX_COUNT):
            print(post)


class TestInstaloaderLoggedIn(TestInstaloaderAnonymously):

    def setUp(self):
        super().setUp()
        self.L.load_session_from_file(OWN_USERNAME)

    @unittest.skip('')
    def test_stories_download(self):
        self.L.download_stories()

    @unittest.skip('')
    def test_private_profile_download(self):
        self.L.download_profiles({self.L.check_profile_id(PRIVATE_PROFILE)}, stories=True, raise_errors=True)

    def test_stories_paging(self):
        for user_story in self.L.get_stories():
            print("profile {}.".format(user_story.owner_username))
            for item in user_story.get_items():
                print(item)

    def test_highlights_paging(self):
        for user_highlight in self.L.get_highlights(PROFILE_WITH_HIGHLIGHTS):
            print("Retrieving {} highlights \"{}\" from profile {}".format(user_highlight.itemcount,
                                                                           user_highlight.title,
                                                                           user_highlight.owner_username))
            for item in user_highlight.get_items():
                print(item)

    def test_private_profile_paging(self):
        self.post_paging_test(instaloader.Profile.from_username(self.L.context, PRIVATE_PROFILE).get_posts())

    def test_feed_download(self):
        self.L.download_feed_posts(NORMAL_MAX_COUNT)

    def test_feed_paging(self):
        for count, post in enumerate(self.L.get_feed_posts()):
            print(post)
            if count == PAGING_MAX_COUNT:
                break

    def test_saved_download(self):
        self.L.download_saved_posts(NORMAL_MAX_COUNT)

    def test_saved_paging(self):
        for count, post in enumerate(instaloader.Profile.from_username(self.L.context, OWN_USERNAME).get_saved_posts()):
            print(post)
            if count == PAGING_MAX_COUNT:
                break

    def test_test_login(self):
        self.assertEqual(OWN_USERNAME, self.L.test_login())

    def test_followees_and_stories(self):
        profile = instaloader.Profile.from_username(self.L.context, OWN_USERNAME)
        followees = set(islice(profile.get_followees(), PAGING_MAX_COUNT))
        self.L.download_profiles(followees, profile_pic=False, stories=True, posts=False, raise_errors=True)

    def test_get_followees(self):
        profile = instaloader.Profile.from_username(self.L.context, OWN_USERNAME)
        for f in profile.get_followees():
            print(f.username)

    def test_get_followers(self):
        profile = instaloader.Profile.from_username(self.L.context, OWN_USERNAME)
        for f in profile.get_followers():
            print(f.username)

    def test_get_similar_accounts(self):
        profile = instaloader.Profile.from_username(self.L.context, OWN_USERNAME)
        for f in profile.get_similar_accounts():
            print(f.username)

    def test_get_likes(self):
        for post in instaloader.Profile.from_username(self.L.context, OWN_USERNAME).get_posts():
            for like in post.get_likes():
                print(like.username)
            break

    def test_explore_paging(self):
        for count, post in enumerate(self.L.get_explore_posts()):
            print(post)
            if count == PAGING_MAX_COUNT:
                break

    def test_location_download(self):
        self.L.download_location(LOCATION, NORMAL_MAX_COUNT)

    def test_location_paging(self):
        for count, post in enumerate(self.L.get_location_posts(LOCATION)):
            print(post)
            if count == PAGING_MAX_COUNT:
                break


class TestReelsFromClipsPayload(unittest.TestCase):
    """get_reels() must build Posts from the clips connection payload directly,
    rather than issuing one additional metadata request per Reel."""

    def _reel_node(self, **overrides):
        media = {
            "code": "DafxF9DjC0A",
            "pk": "123",
            "media_type": 2,
            "caption": {"text": "ITM Paris"},
            "has_liked": False,
            "like_count": 42,
            "comment_count": 3,
            "taken_at": 1783437404,
            "video_duration": 10,
            "video_versions": [{"url": "https://example.com/reel.mp4"}],
            "view_count": 5970,
            "user": {"pk": "1", "username": "itmparis", "full_name": "ITM Paris"},
            "image_versions2": {"candidates": [{"url": "https://example.com/reel.jpg"}]},
        }
        media.update(overrides)
        return {"media": media}

    def test_builds_post_without_extra_request(self):
        context = Mock(is_logged_in=True)
        profile = Mock()
        profile._context = context

        with patch.object(instaloader.Post, "from_shortcode") as from_shortcode:
            post = instaloader.Profile._reel_from_node(profile, self._reel_node())

        from_shortcode.assert_not_called()
        self.assertEqual(post.shortcode, "DafxF9DjC0A")
        self.assertEqual(post.caption, "ITM Paris")
        self.assertEqual(post.video_view_count, 5970)
        self.assertEqual(post.likes, 42)
        self.assertEqual(post.comments, 3)

    def test_falls_back_to_from_shortcode_on_unknown_media_type(self):
        context = Mock(is_logged_in=True)
        profile = Mock()
        profile._context = context
        fallback_post = Mock()

        with patch.object(instaloader.Post, "from_shortcode", return_value=fallback_post) as from_shortcode:
            post = instaloader.Profile._reel_from_node(
                profile, self._reel_node(media_type=99)
            )

        from_shortcode.assert_called_once_with(context=context, shortcode="DafxF9DjC0A")
        self.assertIs(post, fallback_post)


if __name__ == '__main__':
    unittest.main()
