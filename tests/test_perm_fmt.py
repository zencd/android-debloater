import os
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from src.perm_fmt import PermFileWriter, shorten_perm, normalize_perm, parse_perm_file
from src.logs import log


class TestPermFileWriter(TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.file_path = Path(self.temp_dir.name) / "test_perm_file.txt"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_write_permission(self):
        with PermFileWriter(self.file_path) as writer:
            writer.write_permission("com.example", "android.permission.INTERNET", True)
            writer.write_permission("com.example", "android.permission.CAMERA", False)

        with open(self.file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            self.assertEqual(content, "com.example  INTERNET  grant\ncom.example  CAMERA  revoke\n")

    def test_write_permission_with_shortened_perm(self):
        with PermFileWriter(self.file_path) as writer:
            writer.write_permission("com.example", "android.permission.INTERNET", True)
            writer.write_permission("com.example", "android.permission.CAMERA", False)

        with open(self.file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            self.assertEqual(content, "com.example  INTERNET  grant\ncom.example  CAMERA  revoke\n")

    def test_context_manager(self):
        with PermFileWriter(self.file_path) as writer:
            writer.write_permission("com.example", "android.permission.INTERNET", True)

        self.assertTrue(self.file_path.exists())

    def test_context_manager_exception(self):
        class TestException(Exception):
            pass

        try:
            with PermFileWriter(self.file_path) as writer:
                writer.write_permission("com.example", "android.permission.INTERNET", True)
                raise TestException("Test exception")
        except TestException:
            pass

        self.assertFalse(self.file_path.exists())


class TestPermUtils(TestCase):

    def test_shorten_perm(self):
        self.assertEqual(shorten_perm("android.permission.INTERNET"), "INTERNET")
        self.assertEqual(shorten_perm("com.example.permission.CUSTOM"), "com.example.permission.CUSTOM")
        self.assertEqual(shorten_perm("android.permission"), "android.permission")

    def test_normalize_perm(self):
        self.assertEqual(normalize_perm("INTERNET"), "android.permission.INTERNET")
        self.assertEqual(normalize_perm("com.example.permission.CUSTOM"), "com.example.permission.CUSTOM")
        self.assertEqual(normalize_perm("android.permission.INTERNET"), "android.permission.INTERNET")

    def test_parse_perm_file(self):
        content = """
            com.example1  INTERNET  grant
            com.example2  CAMERA  revoke
            com.example3  LOCATION  grant"""

        with tempfile.NamedTemporaryFile(delete=False, mode='w', encoding='utf-8') as temp_file:
            temp_file.write(content)
            temp_file_path = Path(temp_file.name)

        parsed_permissions = list(parse_perm_file(temp_file_path))
        self.assertEqual(parsed_permissions, [
            ("com.example1", "android.permission.INTERNET", True),
            ("com.example2", "android.permission.CAMERA", False),
            ("com.example3", "android.permission.LOCATION", True),
        ])

        temp_file_path.unlink(missing_ok=True)
