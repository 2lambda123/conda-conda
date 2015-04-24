import unittest
from conda_env.utils.downloader import Downloader
from conda_env.exceptions import EnvironmentUsernameRequired


class TestDownloader(unittest.TestCase):
    def test_parse_full_spec(self):
        username, packagename, version = Downloader.parse("anaconda/conda-env==2.1")
        self.assertEqual(username, 'anaconda')
        self.assertEqual(packagename, 'conda-env')
        self.assertEqual(version, '2.1')

    def test_parse_missing_username(self):
        with self.assertRaises(EnvironmentUsernameRequired):
            Downloader.parse("conda-env==2.1")

    def test_parse_partial_spec(self):
        username, packagename, version = Downloader.parse("anaconda/conda-env")
        self.assertEqual(username, 'anaconda')
        self.assertEqual(packagename, 'conda-env')
        self.assertEqual(version, None)

if __name__ == '__main__':
    unittest.main()
