import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from build_resource import read_baseline, read_snapshot, safe_name, version_key, write_archive


class PackageSafetyTests(unittest.TestCase):
    def test_runtime_and_user_files_are_rejected(self):
        for name in ["python/python.exe", "config/config.json", "runtimes/maa.dll", "agent/__pycache__/x.pyc", "resource/run.log"]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                safe_name(name)

    def test_traversal_and_windows_paths_are_rejected(self):
        for name in ["resource/../../config.json", "/resource/a", "C:/a", "resource\\a", "resource//a", "agent/./a.py"]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                safe_name(name)

    def test_archive_bytes_are_reproducible(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = [Path(folder) / "one.zip", Path(folder) / "two.zip"]
            for path in paths:
                write_archive(path, {"resource/b.txt": b"b", "interface.json": b"{}", "agent/main.py": b"pass\n"})
            self.assertEqual(paths[0].read_bytes(), paths[1].read_bytes())

    def test_baseline_checksum_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "source.zip"
            write_archive(path, {"interface.json": b"{}"})
            with self.assertRaises(ValueError):
                read_baseline(path, "0" * 64)

    def test_case_collision_in_archive_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "source.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("resource/A.txt", b"a")
                archive.writestr("resource/a.txt", b"b")
            with self.assertRaises(ValueError):
                read_baseline(path, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_test_versions_sort_numerically(self):
        self.assertGreater(version_key("v1.0.7-beta.10"), version_key("v1.0.7-beta.9"))
        for version in ["latest", "v1.0.7", "v1.0.7-beta.3;exit", "../v1.0.7-beta.3"]:
            with self.subTest(version=version), self.assertRaises(ValueError):
                version_key(version)

    def test_snapshot_rejects_changed_or_unlisted_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "assets").mkdir()
            source = root / "assets/interface.json"
            source.write_bytes(b"{}")
            metadata = {"repository": "cccrx1/TKFMaa", "base_commit": "a" * 40,
                        "files": {"assets/interface.json": hashlib.sha256(b"{}").hexdigest()}}
            (root / "snapshot.json").write_text(json.dumps(metadata), encoding="utf-8")
            files, _ = read_snapshot(root)
            self.assertEqual(files, {"interface.json": b"{}"})
            source.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                read_snapshot(root)
            source.write_bytes(b"{}")
            (root / "config.json").write_bytes(b"private")
            with self.assertRaisesRegex(ValueError, "inventory differs"):
                read_snapshot(root)


if __name__ == "__main__":
    unittest.main()
