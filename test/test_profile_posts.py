"""Offline tests for fetching profile posts without profile metadata."""

import unittest
from unittest.mock import patch

from instaloader import Instaloader, NodeIterator, Profile
from instaloader.exceptions import (
    AbortDownloadException,
    BadResponseException,
    InvalidArgumentException,
    LoginRequiredException,
)


def timeline(*numbers, cursor=None):
    """Build a small synthetic Instagram timeline response."""
    return {
        "data": {
            "xdt_api__v1__feed__user_timeline_graphql_connection": {
                "edges": [
                    {
                        "node": {
                            "code": f"POST{number}",
                            "pk": str(number),
                            "media_type": 1,
                            "taken_at": 1700000000 + number,
                            "has_liked": False,
                            "like_count": 0,
                        }
                    }
                    for number in numbers
                ],
                "page_info": {
                    "has_next_page": cursor is not None,
                    "end_cursor": cursor,
                },
            }
        }
    }


class TestProfilePosts(unittest.TestCase):
    def setUp(self):
        # Any unexpected real HTTP request must fail the test.
        network = patch(
            "requests.Session.request",
            side_effect=AssertionError("Unexpected HTTP request"),
        )
        network.start()
        self.addCleanup(network.stop)

        self.loader = Instaloader(quiet=True)
        self.addCleanup(self.loader.close)

        # Simulate a loaded session without using real credentials.
        self.loader.context.username = "test_session"

        query = patch.object(
            self.loader.context,
            "doc_id_graphql_query",
            return_value=timeline(),
        )
        self.query = query.start()
        self.addCleanup(query.stop)

    def test_fetches_posts_without_profile_metadata(self):
        self.query.return_value = timeline(1)

        posts = self.loader.get_profile_posts(" @Example ")

        self.assertIsInstance(posts, NodeIterator)
        self.assertEqual([post.shortcode for post in posts], ["POST1"])
        self.query.assert_called_once()

        _, variables, referer = self.query.call_args.args
        self.assertEqual(variables["username"], "example")
        self.assertEqual(referer, "https://www.instagram.com/example/")

    def test_requires_login_before_querying(self):
        self.loader.context.username = None

        with self.assertRaises(LoginRequiredException):
            self.loader.get_profile_posts("example")

        self.query.assert_not_called()

    def test_rejects_invalid_username_before_querying(self):
        for username in ("", "@", "bad/name", "a" * 31):
            with self.subTest(username=username):
                with self.assertRaises(InvalidArgumentException):
                    self.loader.get_profile_posts(username)

        self.query.assert_not_called()

    def test_paginates(self):
        self.query.side_effect = [
            timeline(1, cursor="next-page"),
            timeline(2),
        ]

        posts = list(self.loader.get_profile_posts("example"))

        self.assertEqual(
            [post.shortcode for post in posts],
            ["POST1", "POST2"],
        )
        self.assertEqual(self.query.call_count, 2)
        variables = self.query.call_args.args[1]
        self.assertEqual(variables["after"], "next-page")

    def test_accepts_empty_timeline(self):
        posts = list(self.loader.get_profile_posts("example"))
        self.assertEqual(posts, [])

    def test_rejects_missing_timeline(self):
        for response in ({}, {"data": None}, {"data": {}}):
            with self.subTest(response=response):
                self.query.return_value = response

                with self.assertRaises(BadResponseException):
                    self.loader.get_profile_posts("example")

    def test_propagates_account_challenge(self):
        error = AbortDownloadException("challenge_required")
        self.query.side_effect = error

        with self.assertRaises(AbortDownloadException) as raised:
            self.loader.get_profile_posts("example")

        self.assertIs(raised.exception, error)
        self.query.assert_called_once()

    def test_preserves_freeze_and_thaw(self):
        self.query.return_value = timeline(1, 2, 3)

        original = self.loader.get_profile_posts("example")
        next(original)
        next(original)
        frozen = original.freeze()

        resumed = self.loader.get_profile_posts("example")
        resumed.thaw(frozen)

        # NodeIterator intentionally replays the last yielded item.
        self.assertEqual(
            [post.shortcode for post in resumed],
            ["POST2", "POST3"],
        )

    def test_existing_authenticated_profile(self):
        self.query.return_value = timeline(1)
        profile = Profile(
            self.loader.context,
            {"id": "123", "username": "example"},
        )

        with patch.object(profile, "_obtain_metadata") as metadata:
            posts = list(profile.get_posts())
            metadata.assert_called_once_with()

        self.assertEqual([post.shortcode for post in posts], ["POST1"])
        self.assertEqual(
            self.query.call_args.args[1]["username"], "example"
        )

    def test_existing_anonymous_pagination(self):
        self.loader.context.username = None

        def page(number, cursor=None):
            return {
                "edges": [
                    {
                        "node": {
                            "shortcode": f"POST{number}",
                            "id": str(number),
                            "__typename": "GraphImage",
                            "is_video": False,
                            "date": 1700000000 + number,
                        }
                    }
                ],
                "page_info": {
                    "has_next_page": cursor is not None,
                    "end_cursor": cursor,
                },
            }

        profile = Profile(
            self.loader.context,
            {
                "id": "123",
                "username": "example",
                "edge_owner_to_timeline_media": page(1, "next-page"),
            },
        )
        self.query.return_value = {
            "data": {
                "user": {
                    "edge_owner_to_timeline_media": page(2),
                }
            }
        }

        with patch.object(profile, "_obtain_metadata"):
            posts = profile.get_posts()
            self.query.assert_not_called()
            self.assertEqual(
                [post.shortcode for post in posts],
                ["POST1", "POST2"],
            )

        self.query.assert_called_once()
        doc_id, variables, _ = self.query.call_args.args
        self.assertEqual(doc_id, "7950326061742207")
        self.assertEqual(variables["id"], 123)
        self.assertEqual(variables["after"], "next-page")