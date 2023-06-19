from instaloader.structures import Post

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


if __name__ == '__main__':
    unittest.main()