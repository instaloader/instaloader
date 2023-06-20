from instaloader.structures import Post
from instaloader import instaloadercontext
from instaloader.exceptions import InvalidArgumentException

import unittest

class TestesUnitarios(unittest.TestCase):

    def test_has_rigth_amount_valid_graphql_types(self):
        len_graphql_types_subject = len(Post.supported_graphql_types())

        self.assertEqual(len_graphql_types_subject, 3)
    
    def test_has_all_valid_graphql_types(self):
        expected_graphql_types = ["GraphImage", "GraphVideo", "GraphSidecar"]
        graphql_types = Post.supported_graphql_types()  
        
        has_all_graphql_types = all(
            graphql_type in expected_graphql_types
                for graphql_type in graphql_types)

        self.assertTrue(has_all_graphql_types)
    
    def test_has_valid_user_agent(self):
        expected_user_agent = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 ' \
           '(KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36'
        
        user_agent_subject = instaloadercontext.default_user_agent()

        self.assertEqual(user_agent_subject, expected_user_agent)
    
    def test_too_long_media_id_should_raise_invalid_argument_exception(self):
        invalid_media_id = 10 ** 100

        self.assertRaises(InvalidArgumentException, lambda: Post.mediaid_to_shortcode(invalid_media_id))
    
    def test_negative_media_id_should_raise_invalid_argument_exception(self):
        invalid_media_id = -1

        self.assertRaises(OverflowError, lambda: Post.mediaid_to_shortcode(invalid_media_id))
    
    def test_valid_mediaid_to_shortcode(self):
        result = Post.mediaid_to_shortcode(1)

        self.assertEqual(result, 'B')


if __name__ == '__main__':
    unittest.main()