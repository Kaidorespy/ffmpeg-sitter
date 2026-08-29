import importlib.machinery
import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path


SOURCE = Path(__file__).parents[1] / "ffmpeg-sitter.py"
loader = importlib.machinery.SourceFileLoader("ffmpeg_sitter", str(SOURCE))
spec = importlib.util.spec_from_loader(loader.name, loader)
app = importlib.util.module_from_spec(spec)
loader.exec_module(app)


class PathTests(unittest.TestCase):
    def test_exact_path_detection_avoids_prefix_false_positive(self):
        value = r"C:\Tools\ffmpeg\bin-old;C:\Windows"
        self.assertFalse(app.path_contains(value, r"C:\Tools\ffmpeg\bin"))

    def test_add_path_entry_is_idempotent(self):
        value = r"C:\Windows;C:\Tools\ffmpeg\bin"
        self.assertEqual(app.add_path_entry(value, r"c:\tools\FFMPEG\bin"), value)

    def test_remove_path_entry_preserves_other_entries(self):
        value = r"C:\Windows;C:\Tools\ffmpeg\bin;C:\Other"
        self.assertEqual(app.remove_path_entry(value, r"C:\Tools\ffmpeg\bin"), r"C:\Windows;C:\Other")

    def test_deduplicates_children_and_repeated_targets(self):
        paths = [r"C:\Temp\ffmpeg", r"C:\Temp\ffmpeg\bin", r"C:\Temp\ffmpeg"]
        self.assertEqual(app.deduplicate_paths(paths), [r"C:\Temp\ffmpeg"])


class CleanupTests(unittest.TestCase):
    def test_loose_desktop_executable_does_not_target_desktop(self):
        target = app.cleanup_target(r"C:\Users\Casey\Desktop")
        self.assertEqual(target, r"C:\Users\Casey\Desktop\ffmpeg.exe")

    def test_named_ffmpeg_install_targets_its_root(self):
        target = app.cleanup_target(r"C:\Tools\ffmpeg-release\bin")
        self.assertEqual(target, r"C:\Tools\ffmpeg-release")


class ArchiveTests(unittest.TestCase):
    def test_rejects_parent_directory_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "bad.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("../outside.exe", b"bad")
            with zipfile.ZipFile(archive) as zf:
                with self.assertRaises(ValueError):
                    app.safe_zip_members(zf)

    def test_accepts_normal_archive_members(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "good.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("ffmpeg/bin/ffmpeg.exe", b"ok")
            with zipfile.ZipFile(archive) as zf:
                self.assertEqual(len(app.safe_zip_members(zf)), 1)


if __name__ == "__main__":
    unittest.main()
