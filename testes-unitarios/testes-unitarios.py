import os
import getpass
import unittest
from unittest.mock import patch

from instaloader import instaloader
USUARIO_TESTE = 'kaell_andrade'
WINDOS = 'Windows'
UNIX = 'Unix'

class TestesUnitarios(unittest.TestCase):

    @patch('platform.system')
    def test_windows_localappdata_get_config_dir(self, mock_system):
        mock_system.return_value = WINDOS
        os.environ["LOCALAPPDATA"] = "C:\\Users\\{}\\AppData\\Local".format(USUARIO_TESTE)
        expected_dir = os.path.normpath("C:\\Users\\{}\\AppData\Local/Instaloader".format(USUARIO_TESTE))
        self.assertEqual(instaloader._get_config_dir(), expected_dir)
    
    @patch('platform.system')
    def test_windows_fallback_get_config_dir(self, mock_system):
        mock_system.return_value = WINDOS
        getpass.getuser = lambda: USUARIO_TESTE
        expected_dir = os.path.normpath("/tmp/.instaloader-{}".format(USUARIO_TESTE))
        self.assertEqual(instaloader._get_config_dir(), expected_dir)
    
    @patch('platform.system')
    def test_unix_get_config_dir(self, mock_system):
        mock_system.return_value = UNIX
        os.environ["XDG_CONFIG_HOME"] = "/home/{}/.config".format(USUARIO_TESTE)
        expected_dir = "/home/{}/.config/instaloader".format(USUARIO_TESTE)
        self.assertEqual(instaloader._get_config_dir(), expected_dir)
    
    @patch('platform.system')
    def test_windows_get_default_session_filename(self, mock_system):
        mock_system.return_value = WINDOS
        os.environ["LOCALAPPDATA"] = "C:\\Users\\testuser\\AppData\\Local"
        expected_filename = "C:\\Users\\testuser\\AppData\\Local/Instaloader/session-{}".format(USUARIO_TESTE)
        self.assertEqual(instaloader.get_default_session_filename(USUARIO_TESTE), expected_filename)

    @patch('platform.system')
    def test_unix_get_default_session_filename(self, mock_system):
        mock_system.return_value = UNIX
        os.environ["XDG_CONFIG_HOME"] = "/home/testuser/.config"
        expected_filename = "/home/testuser/.config/instaloader/session-{}".format(USUARIO_TESTE)
        self.assertEqual(instaloader.get_default_session_filename(USUARIO_TESTE), expected_filename)

if __name__ == '__main__':
    unittest.main()