import unittest
from src.utils import extract_block

class TestExtractBlock(unittest.TestCase):

    def test_extract_block_basic(self):
        lines = [
            "start",
            "line1",
            "line2",
            "end"
        ]
        result = extract_block(lines, r"^start$", r"^end$")
        self.assertEqual(result, ["start", "line1", "line2"])

    def test_extract_block_no_start(self):
        lines = [
            "line1",
            "line2",
            "end"
        ]
        result = extract_block(lines, r"^start$", r"^end$")
        self.assertEqual(result, [])

    def test_extract_block_no_end(self):
        lines = [
            "start",
            "line1",
            "line2"
        ]
        result = extract_block(lines, r"^start$", r"^end$")
        self.assertEqual(result, ["start", "line1", "line2"])

    def test_extract_block_empty_lines(self):
        lines = [
            "start",
            "",
            "line1",
            "",
            "end"
        ]
        result = extract_block(lines, r"^start$", r"^end$")
        self.assertEqual(result, ["start", "", "line1", ""])

    def test_extract_block_nothing_between(self):
        lines = [
            "start",
            "end"
        ]
        result = extract_block(lines, r"^start$", r"^end$")
        self.assertEqual(result, ["start"])

    def test_extract_block_multiple_starts(self):
        lines = [
            "start",
            "line1",
            "start",
            "line2",
            "end"
        ]
        result = extract_block(lines, r"^start$", r"^end$")
        self.assertEqual(result, ["start", "line1", "start", "line2"])

    def test_extract_block_multiple_ends(self):
        lines = [
            "start",
            "line1",
            "end",
            "line2",
            "end"
        ]
        result = extract_block(lines, r"^start$", r"^end$")
        self.assertEqual(result, ["start", "line1"])

    def test_extract_block_no_end_pattern(self):
        lines = [
            "start",
            "line1",
            "line2"
        ]
        result = extract_block(lines, r"^start$", r"^end$")
        self.assertEqual(result, ["start", "line1", "line2"])

if __name__ == '__main__':
    unittest.main()
