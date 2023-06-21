import unittest

"""
Para executar esse teste, faz-se necessario estar no diretorio instaloader-tests e executar o comando:

python3 -m testes-unitarios.testes-unitarios
"""



from instaloader.instaloadercontext import InstaloaderContext
from instaloader.instaloader import Instaloader
from instaloader.structures import Post, Profile



import datetime




class MockTestsPost:
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
        # print(profile, post2)
        # print('aqui', post.shortcode)
        # print('title', post2.title)
        print('post')
        print( post2.title)
    
    def util_datetime(self):
        return datetime.datetime.fromtimestamp(self.timestamp)
    
    @property
    def mockpost(self):
        return  {   
                'owner': 'gabriel', 
                'shortcode': 'shortcode123', #Cs894TXOetY
                'code': 'shortcode123',
                'id': '1234', 
                'title': 'post da ufs', 
                'date': self.timestamp, 
                'taken_at_timestamp': self.timestamp
                }
    





class TestesUnitarios(unittest.TestCase):

    data_tests = MockTestsPost()
    mockpost = data_tests.mockpost
    timestamp = data_tests.timestamp
    context = data_tests.instaLoader.context

    def test_local_date_with_date_key(self):
        print('test_local_date_with_date_key')
        from_timestamp = self.data_tests.util_datetime().astimezone()

        post = Post(self.context, self.mockpost)

        self.assertEqual(post.date_local, from_timestamp)
    
    def test_local_date_without_date_key(self):
        print('test_local_date_without_date_key')
        copy_date = self.mockpost.copy()
        del copy_date['date']

        from_timestamp = self.data_tests.util_datetime().astimezone()

        post = Post(self.context, self.mockpost)

        self.assertEqual(post.date_local, from_timestamp)
    
    def test_with_title_post(self):
        print('test_with_title_post')
        title = 'post da ufs'

        post = Post(self.context,  self.mockpost)
        
        self.assertEqual(post.title, title)
    

    def test_without_title_post(self):
        print('test_without_title_post')
        title = None
        copymock = self.mockpost.copy()

        del copymock['title']
        post = Post(self.context, copymock)
        post._full_metadata_dict = {'teste': 'title'}

        self.assertEqual( post.title, title)


    def test_media_id(self):
        print('test_media_id')
        mediaid = 1234
        post = Post(self.context,  self.mockpost)

        self.assertEqual(mediaid, post.mediaid)
    
    

    def test_shortcode_with_shortcode_key(self):
        print('test_shortcode_with_shortcode_key')
        shortcode = 'shortcode123'
        post = Post(self.context, self.mockpost)

        self.assertEqual(post.shortcode, shortcode)
    
    def test_shortcode_without_shortcode_key(self):
        print('test_shortcode_without_shortcode_key')
        shortcode = 'shortcode123'

        copymock = self.mockpost.copy()
        del copymock['shortcode']

        post = Post(self.context, copymock)

        self.assertEqual(post.shortcode, shortcode)

   

if __name__ == '__main__':

    unittest.main()