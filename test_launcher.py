"""Focused launcher tests; no real browser, process, or listening server."""
import importlib.util
import os
import pathlib
import tempfile
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location("launcher", pathlib.Path(__file__).with_name("launcher.py"))
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)


class LauncherTests(unittest.TestCase):
    def test_port_validation_and_environment(self):
        with mock.patch.dict(os.environ, {"ARCH_TRAINER_PORT": "9123"}):
            self.assertEqual(launcher.parse_port(), 9123)
        for bad in ("0", "65536", "abc"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                launcher.parse_port(bad)

    def test_existing_own_server_is_reused_without_child(self):
        with mock.patch.object(launcher, "is_our_server", return_value=True), \
             mock.patch.object(launcher.subprocess, "Popen") as popen:
            self.assertTrue(launcher.launch_server(8784))
            popen.assert_not_called()

    def test_foreign_listener_is_refused_without_child(self):
        with mock.patch.object(launcher, "is_our_server", return_value=False), \
             mock.patch.object(launcher, "port_is_free", return_value=False), \
             mock.patch.object(launcher.subprocess, "Popen") as popen:
            with self.assertRaisesRegex(RuntimeError, "занят другой программой"):
                launcher.launch_server(8784)
            popen.assert_not_called()

    def test_health_check_rejects_another_app(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, size): return b'{"app":"some-other-service"}'
        opener = mock.Mock()
        opener.open.return_value = Response()
        with mock.patch.object(launcher.urllib.request, "build_opener", return_value=opener):
            self.assertFalse(launcher.is_our_server(8784))

    def test_delayed_health_after_child_binds_is_allowed(self):
        with tempfile.TemporaryDirectory() as folder:
            process = mock.Mock()
            process.poll.return_value = None
            patches = [
                mock.patch.object(launcher, "is_our_server", side_effect=[False, False, True]),
                mock.patch.object(launcher, "port_is_free", return_value=True),
                mock.patch.object(launcher, "state_directory", return_value=pathlib.Path(folder)),
                mock.patch.object(launcher.subprocess, "Popen", return_value=process),
                mock.patch.object(launcher.time, "monotonic", side_effect=[0, 0, 1]),
                mock.patch.object(launcher.time, "sleep"),
            ]
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
                self.assertTrue(launcher.launch_server(8784, wait_seconds=2))
                process.poll.assert_called_once()

    def test_launch_race_does_not_claim_a_foreign_listener(self):
        with tempfile.TemporaryDirectory() as folder:
            patches = [
                mock.patch.object(launcher, "is_our_server", side_effect=[False, False, False]),
                mock.patch.object(launcher, "port_is_free", side_effect=[True, False]),
                mock.patch.object(launcher, "state_directory", return_value=pathlib.Path(folder)),
                mock.patch.object(launcher.subprocess, "Popen"),
                mock.patch.object(launcher.time, "sleep"),
            ]
            with patches[0], patches[1], patches[2], patches[3] as popen, patches[4]:
                with self.assertRaisesRegex(RuntimeError, "Запуск отменён"):
                    launcher.launch_server(8784)
                popen.assert_called_once()

    def test_state_directory_is_per_user_and_overrideable(self):
        with mock.patch.dict(os.environ, {"LOCALAPPDATA": r"C:\Users\Ada\AppData\Local"}, clear=True), \
             mock.patch.object(launcher.os, "name", "nt"), mock.patch.object(launcher.pathlib, "Path", pathlib.PureWindowsPath):
            self.assertEqual(str(launcher.state_directory()), r"C:\Users\Ada\AppData\Local\ArchitecturePractice")
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(os.environ, {"ARCH_TRAINER_STATE_DIR": folder}):
            self.assertEqual(launcher.state_directory(), pathlib.Path(folder))

    def test_child_commands_source_and_frozen(self):
        with mock.patch.object(launcher.sys, "frozen", False, create=True), \
             mock.patch.object(launcher.sys, "executable", "/usr/bin/python3"):
            self.assertEqual(launcher.child_command(), ["/usr/bin/python3", "-B", str(pathlib.Path(launcher.__file__).resolve()), "--serve"])
        with mock.patch.object(launcher.sys, "frozen", True, create=True), \
             mock.patch.object(launcher.sys, "executable", "C:\\App\\ArchitecturePractice.exe"):
            self.assertEqual(launcher.child_command(), ["C:\\App\\ArchitecturePractice.exe", "--serve"])

    def test_windows_error_dialog_only_for_interactive_launch(self):
        with mock.patch.object(launcher.os, "name", "nt"):
            with mock.patch.object(launcher, "launch_server", side_effect=RuntimeError("occupied")):
                with mock.patch.object(launcher, "show_windows_error") as show_error:
                    with mock.patch.object(launcher.sys, "stderr"):
                        self.assertEqual(launcher.main([]), 1)
                    show_error.assert_called_once()
                    show_error.reset_mock()
                    with mock.patch.object(launcher.sys, "stderr"):
                        self.assertEqual(launcher.main(["--no-open"]), 1)
                    show_error.assert_not_called()


if __name__ == "__main__":
    unittest.main()
