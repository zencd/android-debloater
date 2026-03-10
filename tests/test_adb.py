import unittest
from unittest.mock import patch, MagicMock
from src import adb

class TestAdbModule(unittest.TestCase):
    @patch('src.adb.exec_')
    def test_list_device_enabled_packages(self, mock_exec):
        # Mock the exec_ function to return a known output
        mock_exec.return_value = (0, 'package:com.example1\npackage:com.example2', '')
        expected_output = {'com.example1', 'com.example2'}
        self.assertEqual(adb.list_device_enabled_packages(), expected_output)

    @patch('src.adb.exec_')
    def test_list_device_all_packages(self, mock_exec):
        # Mock the exec_ function to return a known output
        mock_exec.return_value = (0, 'package:com.example1\npackage:com.example2', '')
        expected_output = {'com.example1', 'com.example2'}
        self.assertEqual(adb.list_device_all_packages(), expected_output)

    @patch('src.adb.exec_')
    def test_list_device_user_installed_packages(self, mock_exec):
        # Mock the exec_ function to return a known output
        mock_exec.return_value = (0, 'package:com.example1\npackage:com.example2', '')
        expected_output = {'com.example1', 'com.example2'}
        self.assertEqual(adb.list_device_user_installed_packages(), expected_output)

    @patch('src.adb.exec_')
    def test_grant_or_revoke(self, mock_exec):
        # Mock the exec_ function to return a known output
        mock_exec.return_value = (0, '', '')
        self.assertTrue(adb.grant_or_revoke('com.example1', 'permission1', True))

    @patch('src.adb.exec_')
    def test_set_permission_flag(self, mock_exec):
        # Mock the exec_ function to return a known output
        mock_exec.return_value = (0, '', '')
        self.assertTrue(adb.set_permission_flag('com.example1', 'permission1', 'FLAG'))

    @patch('src.adb.exec_')
    def test_install_multiple(self, mock_exec):
        # Mock the exec_ function to return a known output
        mock_exec.return_value = (0, '', '')
        self.assertEqual(adb.install_multiple(['path1', 'path2']), 0)

    @patch('src.adb.exec_')
    def test_pull_apk(self, mock_exec):
        # Mock the exec_ function to return a known output
        mock_exec.return_value = (0, '', '')
        self.assertIsNone(adb.pull_apk('path1'))

    @patch('src.adb.dumpsys_package')
    def test_read_user_set_permissions(self, mock_dumpsys_package):
        # Mock the dumpsys_package function to return a known output
        mock_dumpsys_package.return_value = ['Packages:', '  package1:', '    permission1: granted=true flags=[USER_SET]']
        expected_output = [('permission1', True, True)]
        self.assertEqual(list(adb.read_user_set_permissions('package1')), expected_output)

    @patch('src.adb.exec_')
    def test_dumpsys_package(self, mock_exec):
        # Mock the exec_ function to return a known output
        mock_exec.return_value = (0, 'Package info', '')
        expected_output = ['Package info']
        self.assertEqual(adb.dumpsys_package('com.example1'), expected_output)

    @patch('src.adb.exec_')
    def test_uninstall_package(self, mock_exec):
        # Mock the exec_ function to return a known output
        mock_exec.return_value = (0, '', '')
        self.assertEqual(adb.uninstall_package('com.example1'), (0, '', ''))

    @patch('src.adb.exec_')
    def test_install_existing_package(self, mock_exec):
        # Mock the exec_ function to return a known output
        mock_exec.return_value = (0, '', '')
        self.assertEqual(adb.install_existing_package('com.example1'), (0, '', ''))

    @patch('src.adb.exec_')
    def test_disable_package(self, mock_exec):
        # Mock the exec_ function to return a known output
        mock_exec.return_value = (0, '', '')
        self.assertEqual(adb.disable_package('com.example1'), (0, '', ''))

    @patch('src.adb.exec_')
    def test_enable_package(self, mock_exec):
        # Mock the exec_ function to return a known output
        mock_exec.return_value = (0, '', '')
        self.assertEqual(adb.enable_package('com.example1'), (0, '', ''))

    @patch('src.adb.uninstall_package')
    @patch('src.adb.disable_package')
    def test_uninstall_or_disable_package(self, mock_uninstall_package, mock_disable_package):
        # Mock the uninstall_package and disable_package functions to return a known output
        mock_uninstall_package.return_value = (1, '', '')
        mock_disable_package.return_value = (0, '', '')
        self.assertEqual(adb.uninstall_or_disable_package('com.example1'), (0, '', ''))

    @patch('src.adb.exec_')
    def test_list_apk_paths_on_device(self, mock_exec):
        # Mock the exec_ function to return a known output
        mock_exec.return_value = (0, '/path/to/package1.apk', '')
        expected_output = {'/path/to/package1.apk'}
        self.assertEqual(adb.list_apk_paths_on_device('com.example1'), expected_output)

    @patch('src.adb.exec_')
    def test_extract_package_names(self, mock_exec):
        lines = ['package:com.example1', 'package:com.example2']
        expected_output = ['com.example1', 'com.example2']
        self.assertEqual(adb.extract_package_names(lines), expected_output)

    @patch('src.adb.exec_')
    def test_read_device_name(self, mock_exec):
        # Mock the exec_ function to return a known output
        mock_exec.side_effect = [(0, 'Brand', ''), (0, 'Model', '')]
        expected_output = ('Brand Model', '')
        self.assertEqual(adb.read_device_name(), expected_output)

if __name__ == "__main__":
    unittest.main()
