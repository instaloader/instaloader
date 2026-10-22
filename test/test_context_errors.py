"""Offline regression tests for request errors."""

import unittest
from unittest.mock import Mock

from instaloader import InstaloaderContext
from instaloader.exceptions import TooManyRequestsException


class TestRateLimitException(unittest.TestCase):
    def test_preserves_exception_after_last_attempt(self):
        for attempts in (1, 3):
            with self.subTest(attempts=attempts):
                context = InstaloaderContext(
                    sleep=False,
                    quiet=True,
                    max_connection_attempts=attempts,
                    rate_controller=Mock(),
                )
                self.addCleanup(context.close)

                response = Mock(
                    status_code=429,
                    reason="Too Many Requests",
                    url="https://www.instagram.com/test/",
                    is_redirect=False,
                )
                response.json.return_value = {
                    "status": "fail",
                    "message": "Please wait",
                }
                session = Mock()
                session.get.return_value = response

                with self.assertRaises(TooManyRequestsException):
                    context.get_json("test/", {}, session=session)

                self.assertEqual(session.get.call_count, attempts)