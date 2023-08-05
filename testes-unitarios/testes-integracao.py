

import unittest


# execute python3 -m testes-unitarios.testes-integracao

class IntegrationTests(unittest.TestCase):
    def test_hello_world(self):
        self.assertEqual('hello', 'hello')


if __name__== '__main__':
    unittest.main()