import pytest
import unittest
import sys
from os.path import join
import os
from shutil import rmtree
from conda.compat import text_type

from conda import noarch

try:
    from unittest.mock import patch, Mock
except ImportError:
    from mock import patch, Mock


def stub_sys_platform(platform):
    def sys_platform(func):
        def func_wrapper(plat):
            sys_plat = sys.platform
            sys.platform = platform
            func(plat)
            sys.platform = sys_plat
        return func_wrapper
    return sys_platform


def setup_info_dir(info_dir):
    os.mkdir(info_dir)
    entry_point_info = '{"type": "python", "entry_points": ["cmd = module.foo:func"]}'
    with open(join(info_dir, "noarch.json"), "w") as noarch_json:
        noarch_json.write(entry_point_info)


def setup_env_for_linkning(prefix):
    src_dir = join(prefix, "src_test")
    os.mkdir(src_dir)
    info_dir = join(src_dir, "info")
    setup_info_dir(info_dir)

    os.mkdir(join(src_dir, "python-scripts"))
    os.mkdir(join(src_dir, "site-packages"))
    os.mkdir(join(prefix, 'conda-meta'))

    open(join(src_dir, "python-scripts/test3"), 'a').close()
    open(join(src_dir, "site-packages/test2"), 'a').close()

    file_content = ["test1", "site-packages/test2", "python-scripts/test3"]
    with open(join(info_dir, "files"), "w") as f:
        for content in file_content:
            f.write("%s\n" % content)


class TestHelpers(unittest.TestCase):

    def test_get_noarch_cls(self):
        self.assertEquals(noarch.get_noarch_cls("python"), noarch.NoArchPython)
        self.assertEquals(noarch.get_noarch_cls("none"), noarch.NoArch)
        self.assertEquals(noarch.get_noarch_cls(True), noarch.NoArch)
        self.assertEquals(noarch.get_noarch_cls(None), None)

    @stub_sys_platform("win32")
    def test_get_site_packages_dir_win(self):
        site_packages_dir = noarch.get_site_packages_dir("")
        self.assertEquals(site_packages_dir, "Lib")

    @stub_sys_platform("darwin")
    def test_get_site_packages_dir_unix(self):
        with patch.object(noarch, "get_python_version_for_prefix", return_value="3.5") as m:
            site_packages_dir = noarch.get_site_packages_dir("")
            self.assertEquals(site_packages_dir, 'lib/python3.5')

    @stub_sys_platform("win32")
    def test_get_bin_dir_win(self):
        bin_dir = noarch.get_bin_dir("")
        self.assertEquals(bin_dir, "Scripts")

    @stub_sys_platform("darwin")
    def test_get_bin_dir_unix(self):
        bin_dir = noarch.get_bin_dir("")
        self.assertEquals(bin_dir, "bin")

    @patch("conda.noarch.get_python_version_for_prefix", return_value="2")
    @patch("subprocess.call")
    def test_compile_missing_pyc(self, get_python_version, subprocess_call):
        noarch.compile_missing_pyc("", ["test.py"], "")
        subprocess_call.called_with(["python", '-Wi', '-m', 'py_compile', "test.py"], cwd="")


class TestEntryPointCreation(unittest.TestCase):

    @pytest.fixture(autouse=True)
    def setup(self, tmpdir):
        self.tmpdir = tmpdir
        setup_info_dir(join(text_type(tmpdir), "info"))

    @stub_sys_platform("darwin")
    def test_create_entry_points_unix(self):
        tmpdir = text_type(self.tmpdir)
        src_dir = tmpdir
        bin_dir = join(tmpdir, "tmp_bin")
        entry_point = join(bin_dir, "cmd")
        os.mkdir(bin_dir)
        prefix = ""
        entry_point_content = """\
#!bin/python
if __name__ == '__main__':
    import sys
    import module.foo

    sys.exit(module.foo.func())
"""
        noarch.create_entry_points(src_dir, bin_dir, prefix)
        self.assertTrue(os.path.isfile(entry_point))
        with open(entry_point, 'r') as script:
            data = script.read()
            self.assertEqual(data, entry_point_content)

    @stub_sys_platform("win32")
    def test_create_entry_points_win(self):
        tmpdir = text_type(self.tmpdir)
        src_dir = tmpdir
        bin_dir = join(tmpdir, "tmp_bin")
        entry_point = join(bin_dir, "cmd-script.py")
        os.mkdir(bin_dir)
        cli_script_src = join(src_dir, 'cli-64.exe')
        cli_script_dst = join(bin_dir, "cmd.exe")
        open(cli_script_src, 'a').close()
        prefix = ""
        entry_point_content = """\
if __name__ == '__main__':
    import sys
    import module.foo

    sys.exit(module.foo.func())
"""

        noarch.create_entry_points(src_dir, bin_dir, prefix)
        self.assertTrue(os.path.isfile(entry_point))
        self.assertTrue(os.path.isfile(cli_script_dst))
        with open(entry_point, 'r') as script:
            data = script.read()
            self.assertEqual(data, entry_point_content)


class TestEntryLinkFiles(unittest.TestCase):

    @pytest.fixture(autouse=True)
    def setup(self, tmpdir):
        self.tmpdir = text_type(tmpdir)
        src_root = join(self.tmpdir, "src_test")
        dst_root = join(self.tmpdir, "dst_test")
        os.mkdir(src_root)
        os.mkdir(dst_root)
        open(join(src_root, "testfile1"), 'a').close()
        open(join(src_root, "testfile2"), 'a').close()

    def check_files(self, files, dst_root, dst_files):
        for f in files:
            dst_file = join(dst_root, f)
            self.assertTrue(os.path.isfile(dst_file))
            self.assertTrue(dst_files.index(dst_file) >= 0)
            os.remove(dst_file)

    def test_link(self):
        prefix = self.tmpdir
        src_root = join(prefix, "src_test")
        dst_root = join(prefix, "dst_test")
        files = ["testfile1", "testfile2"]

        dst_files = noarch.link_files(prefix, src_root, dst_root, files, src_root)
        self.check_files(files, dst_root, dst_files)

    def test_requires_mkdir(self):
        prefix = self.tmpdir
        src_root = join(prefix, "src_test")
        dst_root = join(prefix, "dst_test/not_exist")
        files = ["testfile1", "testfile2"]

        dst_files = noarch.link_files(prefix, src_root, dst_root, files, src_root)
        self.check_files(files, dst_root, dst_files)

    def test_file_already_exists(self):
        prefix = self.tmpdir
        src_root = join(prefix, "src_test")
        dst_root = join(prefix, "dst_test")
        files = ["testfile1", "testfile2"]
        open(join(dst_root, "testfile1"), 'a').close()

        dst_files = noarch.link_files(prefix, src_root, dst_root, files, src_root)
        self.check_files(files, dst_root, dst_files)


class TestNoArch(unittest.TestCase):

    def test_link(self):
        pass


class TestNoArchPythonWindowsLink(unittest.TestCase):

    @pytest.fixture(autouse=True)
    def setup(self, tmpdir):
        self.tmpdir = text_type(tmpdir)
        prefix = self.tmpdir
        setup_env_for_linkning(prefix)
        os.mkdir(join(prefix, "Lib"))
        os.mkdir(join(prefix, "Lib/site-packages"))
        os.mkdir(join(prefix, "Scripts"))

    @stub_sys_platform("win64")
    @patch("conda.install.dist2filename", return_value="test.files")
    def test_link(self, dist2filename):
        prefix = self.tmpdir

        with patch.object(noarch, "get_python_version_for_prefix", return_value="3.5") as m:
            src_dir = join(prefix, "src_test")
            noarch.NoArchPython().link(prefix, src_dir, "dist-test")

        alt_files_path = join(prefix, "conda-meta/test.files")
        self.assertTrue(os.path.isfile(alt_files_path))
        with open(alt_files_path, "r") as alt_files:
            files = alt_files.read().split("\n")[:-1]

        files = [_f.replace('\\', '/') for _f in files]

        self.assertTrue(files.index("Lib/site-packages/test2") >= 0)
        self.assertTrue(files.index("Scripts/test3") >= 0)
        self.assertTrue(os.path.isfile(join(prefix, "Lib/site-packages/test2")))
        self.assertTrue(os.path.isfile(join(prefix, "Scripts/test3")))


class TestNoArchPythonUnixLink(unittest.TestCase):

    @pytest.fixture(autouse=True)
    def setup(self, tmpdir):
        self.tmpdir = text_type(tmpdir)
        prefix = self.tmpdir
        setup_env_for_linkning(prefix)
        os.mkdir(join(prefix, "lib"))
        os.mkdir(join(prefix, "lib/python3.5"))
        os.mkdir(join(prefix, "lib/python3.5/site-packages"))
        os.mkdir(join(prefix, "bin"))

    @stub_sys_platform("darwin")
    @patch("conda.install.dist2filename", return_value="test.files")
    def test_link(self, dist2filename):
        prefix = self.tmpdir
        with patch.object(noarch, "get_python_version_for_prefix", return_value="3.5") as m:
            src_dir = join(prefix, "src_test")
            noarch.NoArchPython().link(prefix, src_dir, "dist-test")

        alt_files_path = join(prefix, "conda-meta/test.files")
        self.assertTrue(os.path.isfile(alt_files_path))
        with open(alt_files_path, "r") as alt_files:
            files = alt_files.read().split("\n")[:-1]

        files = [_f.replace('\\', '/') for _f in files]

        self.assertTrue(files.index("lib/python3.5/site-packages/test2") >= 0)
        self.assertTrue(files.index("bin/test3") >= 0)
        self.assertTrue(os.path.isfile(join(prefix, "lib/python3.5/site-packages/test2")))
        self.assertTrue(os.path.isfile(join(prefix, "bin/test3")))


class TestNoArchPython2Unlink(unittest.TestCase):

    @pytest.fixture(autouse=True)
    def setup(self, tmpdir):
        self.tmpdir = text_type(tmpdir)
        prefix = self.tmpdir
        site_packages = join(prefix, "site-packages")
        os.mkdir(site_packages)
        open(join(site_packages, "testfile1.pyc"), 'a').close()
        open(join(site_packages, "testfile2.py"), 'a').close()
        os.mkdir(join(site_packages, "foo"))
        open(join(site_packages, "foo/testfile3.pyc"), 'a').close()

    @patch("conda.noarch.get_python_version_for_prefix", return_value="2.7")
    def test_unlink(self, get_python_version_for_prefix):
        prefix = self.tmpdir
        dist = ""
        site_packages_dir = join(prefix, "site-packages")
        with patch.object(noarch, "get_site_packages_dir", return_value=self.tmpdir) as g:
            noarch.NoArchPython().unlink(prefix, dist)
            self.assertFalse(os.path.exists(join(site_packages_dir, "testfile1.pyc")))
            self.assertFalse(os.path.exists(join(site_packages_dir, "foo/testfile3.pyc")))
            self.assertTrue(os.path.isfile(join(site_packages_dir, "testfile2.py")))


class TestNoArchPython3Unlink(unittest.TestCase):

    @pytest.fixture(autouse=True)
    def setup(self, tmpdir):
        self.tmpdir = text_type(tmpdir)
        prefix = self.tmpdir
        site_packages = join(prefix, "site-packages")
        os.mkdir(site_packages)
        open(join(site_packages, "testfile1.py"), 'a').close()
        os.mkdir(join(site_packages, "__pycache__"))
        os.mkdir(join(site_packages, "foo"))
        os.mkdir(join(site_packages, "foo/_pycache_"))

    @patch("conda.noarch.get_python_version_for_prefix", return_value="3.2")
    def test_unlink(self, get_python_version_for_prefix):
        prefix = self.tmpdir
        dist = ""
        site_packages_dir = join(prefix, "site-packages")
        with patch.object(noarch, "get_site_packages_dir", return_value=self.tmpdir) as g:
            noarch.NoArchPython().unlink(prefix, dist)
            self.assertFalse(os.path.isdir(join(site_packages_dir, "__pycache__")))
            self.assertFalse(os.path.isdir(join(site_packages_dir, "foo/__pycache__")))
            self.assertTrue(os.path.isdir(join(site_packages_dir, "foo")))
            self.assertTrue(os.path.isfile(join(site_packages_dir, "testfile1.py")))
