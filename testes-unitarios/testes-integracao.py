

import unittest
import instaloader
import tempfile
import os
ratecontroller = None

PERFIL_PUBLICO = 'neymarjr'
ID_PERFIL_PUBLICO = 26669533
EMPTY_PROFILE_ID = 1928659031
EMPTY_PROFILE = "not_public"

'''
Execute: python3 -m testes-unitarios.testes-integracao
'''
class IntegrationTests(unittest.TestCase):
    '''Testes de integração com o instagram'''
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        os.chdir(self.dir)
        self.L = instaloader.Instaloader(download_geotags=True,
                                         download_comments=True,
                                         save_metadata=True)
        self.L.context.raise_all_errors = True
        if ratecontroller is not None:
            ratecontroller._context = self.L.context
            self.L.context._rate_controller = ratecontroller

    
    def test_get_username_id_by_username_public(self):
        self.assertEqual(ID_PERFIL_PUBLICO,
                         instaloader.Profile.from_username(self.L.context, PERFIL_PUBLICO).userid)
    
    def test_get_username_by_name_empty(self):
        self.assertEqual(EMPTY_PROFILE_ID,
                         instaloader.Profile.from_username(self.L.context, EMPTY_PROFILE).userid)
    

if __name__== '__main__':
    unittest.main()