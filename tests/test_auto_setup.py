import importlib.util
import fcntl
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    path = ROOT / 'scripts' / name
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AutoSetupTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((ROOT / 'scripts/auto-setup.py').exists(), 'Missing automatic deb setup')
        self.module = load_script('auto-setup.py')
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        self.root = self.home / 'package'
        self.root.mkdir()
        (self.root / 'PACKAGE_VERSION').write_text('0.3.0-2')
        self.addCleanup(patch.stopall)
        patch.object(self.module, 'ROOT', self.root).start()
        patch.object(self.module.os, 'getuid', return_value=1000).start()
        patch.dict(os.environ, HOME=str(self.home), XDG_DATA_HOME=str(self.home/'data'),
                   XDG_RUNTIME_DIR=str(self.home/'run'), DISPLAY=':99').start()
        self.calls = []

    def run_command(self, command, **kwargs):
        self.calls.append(command)
        return subprocess.CompletedProcess(command, 0)

    def run_setup(self):
        with patch.object(self.module.subprocess, 'run', side_effect=self.run_command):
            return self.module.main([])

    def test_success_is_recorded_and_next_login_does_not_reinstall(self):
        self.assertEqual(self.run_setup(), 0)
        self.assertTrue(any('setup.py' in str(c) for c in self.calls))
        self.calls.clear()
        self.assertEqual(self.run_setup(), 0)
        self.assertEqual(self.calls, [])
        (self.root/'PACKAGE_VERSION').write_text('0.3.0-3')
        self.assertEqual(self.run_setup(), 0)
        self.assertTrue(any('setup.py' in str(c) for c in self.calls))

    def test_failure_is_not_marked_complete_and_can_retry(self):
        def failed(command, **kwargs):
            if 'setup.py' in str(command):
                raise subprocess.CalledProcessError(1, command)
            return self.run_command(command, **kwargs)
        with patch.object(self.module.subprocess, 'run', side_effect=failed):
            self.assertEqual(self.module.main([]), 1)
        self.assertEqual(self.run_setup(), 0)
        self.assertTrue(any('setup.py' in str(c) for c in self.calls))

    def test_same_version_reinstall_initializes_again(self):
        self.assertEqual(self.run_setup(), 0)
        self.calls.clear()
        version = self.root/'PACKAGE_VERSION'
        replacement = self.root/'new-version'
        replacement.write_text(version.read_text())
        replacement.replace(version)
        self.assertEqual(self.run_setup(), 0)
        self.assertTrue(any('setup.py' in str(c) for c in self.calls))

    def test_concurrent_trigger_does_not_run_a_second_installer(self):
        state = self.home/'data/fcitx5-voice'
        state.mkdir(parents=True)
        with (state/'auto-setup.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertEqual(self.run_setup(), 0)
        self.assertEqual(self.calls, [])

    def test_missing_notification_program_does_not_fail_install(self):
        def host(command, **kwargs):
            if command[0] == 'notify-send':
                raise FileNotFoundError()
            return self.run_command(command, **kwargs)
        with patch.object(self.module.subprocess, 'run', side_effect=host):
            self.assertEqual(self.module.main([]), 0)

    def test_login_launch_imports_desktop_environment_and_starts_background_job(self):
        with patch.object(self.module.subprocess, 'run', side_effect=self.run_command):
            self.assertEqual(self.module.main(['--launch']), 0)
        self.assertEqual(self.calls[-1], ['systemctl', '--user', 'start', '--no-block',
                                         'fcitx5-voice-setup.service'])
        imported = next(c for c in self.calls if 'import-environment' in c)
        self.assertIn('DISPLAY', imported)
        self.assertNotIn('HOME', imported)

    def test_non_desktop_and_root_never_initialize(self):
        with patch.object(self.module.os, 'getuid', return_value=0):
            self.assertNotEqual(self.run_setup(), 0)
        with patch.dict(os.environ, DISPLAY='', WAYLAND_DISPLAY=''):
            self.assertNotEqual(self.run_setup(), 0)
        self.assertEqual(self.calls, [])

    def test_missing_package_does_not_keep_retrying_after_removal(self):
        (self.root/'PACKAGE_VERSION').unlink()
        self.assertEqual(self.run_setup(), 0)
        self.assertEqual(self.calls, [])


class PackageSessionTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((ROOT/'scripts/package-session.py').exists(), 'Missing deb lifecycle hook')
        self.module = load_script('package-session.py')
        self.calls = []

    def host(self, command, **kwargs):
        self.calls.append(command)
        if command[0] == 'loginctl':
            return subprocess.CompletedProcess(command, 0, '1000 alice yes active\n1001 bob yes active\n')
        output = 'DISPLAY=:0\n' if 'alice' in command else ''
        return subprocess.CompletedProcess(command, 0, output)

    def test_configure_dispatches_only_to_graphical_user_without_blocking_apt(self):
        from types import SimpleNamespace
        def user(uid):
            name = 'alice' if uid == 1000 else 'bob'
            return SimpleNamespace(pw_name=name, pw_dir='/home/'+name)
        with patch.object(self.module.subprocess, 'run', side_effect=self.host), \
             patch.object(self.module.pwd, 'getpwuid', side_effect=user):
            self.module.main(['configure'])
        starts = [c for c in self.calls if 'start' in c]
        self.assertEqual(len(starts), 1)
        self.assertIn('alice', starts[0])
        self.assertIn('--no-block', starts[0])
        self.assertEqual(starts[0][0], 'runuser')

    def test_missing_logind_defers_to_login_instead_of_breaking_dpkg(self):
        with patch.object(self.module.subprocess, 'run', side_effect=FileNotFoundError):
            self.assertEqual(self.module.main(['configure']), 0)

    def test_remove_stops_setup_and_recognition_for_all_logged_users(self):
        from types import SimpleNamespace
        with patch.object(self.module.subprocess, 'run', side_effect=self.host), \
             patch.object(self.module.pwd, 'getpwuid',
                          return_value=SimpleNamespace(pw_name='alice', pw_dir='/home/alice')):
            self.module.main(['remove'])
        stops = [c for c in self.calls if 'stop' in c]
        self.assertEqual(len(stops), 2)
        self.assertTrue(all('fcitx5-voice-setup.service' in c and 'fcitx5-voice.service' in c for c in stops))

    def test_upgrade_stops_setup_but_keeps_recognizer_available(self):
        from types import SimpleNamespace
        with patch.object(self.module.subprocess, 'run', side_effect=self.host), \
             patch.object(self.module.pwd, 'getpwuid',
                          return_value=SimpleNamespace(pw_name='alice', pw_dir='/home/alice')):
            self.module.main(['upgrade'])
        stops = [c for c in self.calls if 'stop' in c]
        self.assertEqual(len(stops), 2)
        self.assertTrue(all('fcitx5-voice.service' not in c for c in stops))
