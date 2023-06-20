import unittest

"""
Para executar esse teste, faz-se necessario estar no diretorio instaloader-tests e executar o comando:

python3 -m testes-unitarios.testes-unitarios
"""



from instaloader.instaloadercontext import InstaloaderContext
from instaloader.instaloader import Instaloader
from instaloader.structures import Post, Profile

import time



import datetime




class TestsPost:
    def __init__(self) -> None:
        self.instaLoader = Instaloader()
        self.user = 'ufsoficial'
        self.timestamp = 1687140049
        
        # self.__initializeInstaloader()

    def __initializeInstaloader(self) -> None:
        # self.instaLoader.login(self.user, '')
        post = Post.from_shortcode(self.instaLoader.context, 'Cs894TXOetY')
        profile = Profile.from_username(self.instaLoader.context, self.user )

        post2 = Post(self.instaLoader.context, self.mockpost)
        print(profile, post2)
        print('aqui', post.shortcode)
        print('title', post2.title)
        print()
        print('datelocal', post._node.keys())
    
    def util_datetime(self):
        return datetime.datetime.fromtimestamp(self.timestamp)
    @property
    def mockpost(self):
        return  {   
                'owner': 'gabriel', 
                'shortcode': 'Cs894TXOetY', 
                'id': '1234', 
                'title': 'post da ufs', 
                'date': self.timestamp, 
                'taken_at_timestamp': self.timestamp
                }

    

    


        



class TestesUnitarios(unittest.TestCase):

    data_tests = TestsPost()
    mockpost = data_tests.mockpost
    timestamp = data_tests.timestamp



    def test_local_date_with_date_key(self):
        from_timestamp = self.data_tests.util_datetime().astimezone()

        post = Post(self.data_tests.instaLoader.context, self.mockpost)

        self.assertEqual(post.date_local, from_timestamp)
    
    def test_local_date_without_date_key(self):
        copy_date = self.mockpost.copy()
        del copy_date['date']

        from_timestamp = self.data_tests.util_datetime().astimezone()

        post = Post(self.data_tests.instaLoader.context, self.mockpost)

        self.assertEqual(post.date_local, from_timestamp)



    


    

        
        
   

if __name__ == '__main__':
    mock = TestsPost()

    unittest.main()