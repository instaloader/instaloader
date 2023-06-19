import unittest

"""
Para executar esse teste, faz-se necessario estar no diretorio instaloader-tests e executar o comando:

python3 -m testes-unitarios.testes-unitarios
"""



from instaloader.instaloadercontext import InstaloaderContext
from instaloader.instaloader import Instaloader
from instaloader.structures import Post, Profile

import time

timestamp = int(time.time())
print("Timestamp atual:", timestamp, time.time())

import datetime

dt = datetime.datetime.fromtimestamp(timestamp)

print("Data e hora capturadas:", dt)




class MockPost:
    def __init__(self) -> None:
        self.instaLoader = Instaloader()
        self.user = 'ufsoficial'
        self.__initializeInstaloader()
        pass

    def __initializeInstaloader(self) -> None:
        # self.instaLoader.login(self.user, '')
        post = Post.from_shortcode(self.instaLoader.context, 'Cs894TXOetY')
        profile = Profile.from_username(self.instaLoader.context, self.user )

        post2 = Post(self.instaLoader.context, {'shortcode': 'Cs894TXOetY', 'id': '1234', 'title': 'post da ufs', 'date': self.date})
        print(profile, post2)
        print('aqui', post.shortcode)
        print('title', post2.title)
        print('datelocal', type(post.date))
    @property
    def date(self):
        timestamp = 1687140049
        
        return datetime.datetime.fromtimestamp(timestamp)


        



class TestesUnitarios(unittest.TestCase):

    def test_upper(self):
        self.assertEqual('foo'.upper(), 'FOO')

if __name__ == '__main__':
    mock = MockPost()

    unittest.main()