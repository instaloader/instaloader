import os
import getpass
import unittest
from unittest.mock import patch

from instaloader import instaloader
print(instaloader.get_default_session_filename('kaell_andrade'))
USUARIO_TESTE = 'kaell_andrade'
WINDOS = 'Windows'
UNIX = 'Unix'

class TestesUnitarios(unittest.TestCase):

    @patch('platform.system')
    def test_windows_localappdata(self, mock_system):
        mock_system.return_value = WINDOS
        os.environ["LOCALAPPDATA"] = "C:/Users/{}/AppData/Local".format(USUARIO_TESTE)
        expected_dir = os.path.normpath("C:/Users/{}/AppData/Local/Instaloader".format(USUARIO_TESTE))
        self.assertEqual(instaloader._get_config_dir(), expected_dir)
    
    @patch('platform.system')
    def test_windows_fallback(self, mock_system):
        mock_system.return_value = WINDOS
        getpass.getuser = lambda: USUARIO_TESTE
        expected_dir = os.path.normpath("/tmp/.instaloader-{}".format(USUARIO_TESTE))
        self.assertEqual(instaloader._get_config_dir(), expected_dir)

if __name__ == '__main__':
    unittest.main()