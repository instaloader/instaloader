from instaloader.structures import Post
from instaloader import instaloadercontext

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


if __name__ == '__main__':
    unittest.main()