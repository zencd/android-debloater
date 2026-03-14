import unittest
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from src.user_prefs import Resolution, ResolutionList, UserPrefsReader, UserPrefsWriter


class TestUserPrefsReader(unittest.TestCase):
    def test_load_plain_resolutions(self):
        with NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as temp_file:
            temp_file.write("del com.example extra1 extra2 # This is a comment\n")
            temp_file.write("keep com.example2 # Another comment\n")
            temp_file.close()
            reader = UserPrefsReader()
            res_list = reader.load_plain_resolutions(Path(temp_file.name))
            self.assertEqual(len(res_list.items), 2)
            self.assertEqual(res_list.get_resolution('com.example').resolution, 'del')
            self.assertEqual(res_list.get_resolution('com.example2').resolution, 'keep')
            Path(temp_file.name).unlink(missing_ok=True)


class TestUserPrefsWriter(unittest.TestCase):
    def test_dump_resolutions(self):
        with TemporaryDirectory() as temp_dir:
            out_file = Path(temp_dir) / 'user_prefs.txt'
            res_list = ResolutionList()
            res_list.add(
                Resolution(resolution='del', package='com.example', unparsed=['extra1', 'extra2'], comment='comment1'))
            res_list.add(Resolution(resolution='keep', package='com.example2', unparsed=[], comment='Another comment'))
            writer = UserPrefsWriter()
            writer.dump_resolutions(out_file, res_list)
            with open(out_file, 'r', encoding='utf-8') as fp:
                content = fp.readlines()
                self.assertEqual(content[0].strip(), "del  com.example  extra1  extra2        # comment1")
                self.assertEqual(content[1].strip(), "keep  com.example2      # Another comment")


if __name__ == '__main__':
    unittest.main()
