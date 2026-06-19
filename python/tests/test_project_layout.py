import pathlib
import unittest


class ProjectLayoutTest(unittest.TestCase):
    def test_language_owned_source_and_test_roots(self):
        repo_root = pathlib.Path(__file__).resolve().parents[2]

        self.assertFalse((repo_root / "src").exists())
        self.assertFalse((repo_root / "test").exists())
        self.assertFalse((repo_root / "tests").exists())

        self.assertTrue((repo_root / "python" / "src" / "sequence_qsavory_comparison").is_dir())
        self.assertTrue((repo_root / "python" / "tests").is_dir())
        self.assertTrue((repo_root / "julia" / "SeQUeNCeQSavoryComparison" / "src").is_dir())
        self.assertTrue((repo_root / "julia" / "SeQUeNCeQSavoryComparison" / "test").is_dir())
        self.assertTrue((repo_root / "shared" / "configs" / "default.toml").is_file())
