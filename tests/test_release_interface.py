import sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/api"))
from server import byte_range


class VideoRangeTests(unittest.TestCase):
    def test_full_open_and_bounded_range(self):
        self.assertEqual(byte_range(None, 100), (0, 99, False))
        self.assertEqual(byte_range("bytes=0-", 100), (0, 99, True))
        self.assertEqual(byte_range("bytes=10-19", 100), (10, 19, True))
        self.assertEqual(byte_range("bytes=90-200", 100), (90, 99, True))

    def test_suffix_and_invalid_range(self):
        self.assertEqual(byte_range("bytes=-20", 100), (80, 99, True))
        for header in ("bytes=100-", "bytes=10-2", "bytes=-0", "bytes=0-1,3-4", "bad"):
            with self.assertRaises(ValueError):
                byte_range(header, 100)


if __name__ == "__main__":
    unittest.main()
