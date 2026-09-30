from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

import app_runtime


class AppRuntimeTests(unittest.TestCase):
    def test_legacy_cache_migrates_without_overwriting_new_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = root / "cache.json"
            legacy.write_text("old")
            destination = app_runtime.cache_file("cache.json", root)
            self.assertEqual(destination, root / "cache" / "cache.json")
            self.assertEqual(destination.read_text(), "old")
            self.assertFalse(legacy.exists())
            legacy.write_text("other")
            self.assertEqual(app_runtime.cache_file("cache.json", root).read_text(), "old")
            self.assertTrue(legacy.exists())

    def test_source_worker_uses_python_script(self):
        with patch.object(app_runtime.sys, "frozen", False, create=True), \
             patch.object(app_runtime.sys, "executable", "C:/Python/pythonw.exe"):
            command = app_runtime.worker_command()
        self.assertTrue(command[0].endswith("python.exe"))
        self.assertEqual(command[1], "-u")
        self.assertEqual(Path(command[2]).name, "robot_launcher.py")

    def test_frozen_worker_and_portable_data_use_executable_not_extraction_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            executable = str(Path(tmp) / "PriceRobot.exe")
            with patch.object(app_runtime.sys, "frozen", True, create=True), \
                 patch.object(app_runtime.sys, "executable", executable), \
                 patch.dict(os.environ, {}, clear=True):
                self.assertEqual(app_runtime.worker_command(), [executable, "--worker"])
                self.assertEqual(app_runtime.data_directory(), Path(tmp).resolve())

    def test_readonly_install_falls_back_to_user_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(app_runtime.sys, "frozen", True, create=True), \
                 patch.object(app_runtime.tempfile, "TemporaryFile", side_effect=PermissionError), \
                 patch.dict(os.environ, {"LOCALAPPDATA": tmp}, clear=True):
                self.assertEqual(app_runtime.data_directory(), Path(tmp) / "BAP Price Robot")


if __name__ == "__main__":
    unittest.main()
