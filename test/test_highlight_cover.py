import unittest
from unittest.mock import patch

from instaloader.instaloadercontext import InstaloaderContext
from instaloader.structures import Highlight


class HighlightCoverUrlTest(unittest.TestCase):
    def setUp(self):
        self.context = InstaloaderContext(sleep=False, quiet=True)

    def _highlight(self, node):
        return Highlight(self.context, node)

    def test_custom_cover_uses_cropped_url(self):
        thumbnail_src = "https://instagram.example/v/t51.2885-15/e35/111111_n.jpg?_nc_ht=instagram.example"
        cropped_url = "https://scontent.cdninstagram.com/v/t51.2885-15/e35/222222_n.jpg?_nc_ht=scontent.cdninstagram.com"
        highlight = self._highlight({
            "cover_media": {"thumbnail_src": thumbnail_src},
            "cover_media_cropped_thumbnail": {"url": cropped_url},
        })

        self.assertEqual(cropped_url, highlight.cover_url)
        self.assertEqual(cropped_url, highlight.cover_cropped_url)

    def test_auto_cover_size_segment_keeps_thumbnail_src(self):
        thumbnail_src = (
            "https://instagram.fbcdn.net/v/t51.2885-15/s640x640/e35/333333_n.jpg?oe=AAA&oh=BBB"
        )
        cropped_url = (
            "https://other.cdninstagram.com/v/t51.2885-15/p150x150/s150x150/333333_n.jpg"
            "?oe=CCC&ig_cache_key=DDD"
        )
        highlight = self._highlight({
            "cover_media": {"thumbnail_src": thumbnail_src},
            "cover_media_cropped_thumbnail": {"url": cropped_url},
        })

        self.assertEqual(thumbnail_src, highlight.cover_url)

    def test_auto_cover_stp_query_keeps_thumbnail_src(self):
        path = "https://scontent.cdninstagram.com/v/t51.2885-15/444444_n.jpg"
        thumbnail_src = path + "?stp=dst-jpg_s640x640&_nc_ht=scontent.cdninstagram.com"
        cropped_url = path + "?stp=dst-jpg_s150x150&oe=ABCDEF"
        highlight = self._highlight({
            "cover_media": {"thumbnail_src": thumbnail_src},
            "cover_media_cropped_thumbnail": {"url": cropped_url},
        })

        self.assertEqual(thumbnail_src, highlight.cover_url)

    def test_missing_cropped_url_keeps_thumbnail_src(self):
        thumbnail_src = "https://instagram.example/v/t51.2885-15/e35/555555_n.jpg"
        for node in (
            {"cover_media": {"thumbnail_src": thumbnail_src}},
            {"cover_media": {"thumbnail_src": thumbnail_src}, "cover_media_cropped_thumbnail": {}},
            {"cover_media": {"thumbnail_src": thumbnail_src}, "cover_media_cropped_thumbnail": {"url": ""}},
        ):
            with self.subTest(node=node):
                self.assertEqual(thumbnail_src, self._highlight(node).cover_url)

    def test_oversized_urls_skip_comparison(self):
        normal_url = "https://instagram.example/555555_n.jpg"
        for oversized_url in (
            "https://instagram.example/" + "s150x150/" * 1000,
            normal_url + "?signature=" + "a" * 8192,
        ):
            for thumbnail_src, cropped_url in ((normal_url, oversized_url), (oversized_url, normal_url)):
                with self.subTest(oversized_thumbnail=thumbnail_src is oversized_url):
                    highlight = self._highlight({
                        "cover_media": {"thumbnail_src": thumbnail_src},
                        "cover_media_cropped_thumbnail": {"url": cropped_url},
                    })
                    with patch("instaloader.structures.urlsplit") as split:
                        self.assertEqual(cropped_url, highlight.cover_url)
                        split.assert_not_called()

    def test_missing_thumbnail_src_raises_key_error(self):
        cropped = {"cover_media_cropped_thumbnail": {"url": "https://instagram.example/v/t51.2885-15/e35/666666_n.jpg"}}
        for node in (
            cropped,
            {"cover_media": {}, **cropped},
        ):
            with self.subTest(node=node):
                with self.assertRaises(KeyError):
                    self._highlight(node).cover_url


if __name__ == "__main__":
    unittest.main()
