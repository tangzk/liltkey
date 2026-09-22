"""Exercise the installer with isolated homes and simulated host commands."""

import importlib.util
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
REAL_RUN = subprocess.run


class SetupTests(unittest.TestCase):
    def setUp(self):
        script = ROOT / 'scripts/setup.py'
        self.assertTrue(script.is_file(), 'Missing one-command installer')
        spec = importlib.util.spec_from_file_location('voice_setup', script)
        self.setup = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.setup)
        self.temp = tempfile.TemporaryDirectory(prefix='voice setup ')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, HOME=str(self.home),
                   XDG_DATA_HOME=str(self.home / 'data'),
                   XDG_CONFIG_HOME=str(self.home / 'config'),
                   XDG_RUNTIME_DIR=str(self.home / 'run'), DISPLAY=':99').start()
        (self.home / 'run').mkdir()
        patch.object(self.setup.os, 'getuid', return_value=1000).start()
        self.commands = []

    def host_run(self, command, **kwargs):
        command = [str(part) for part in command]
        self.commands.append(command)
        if len(command) > 1 and 'install-user.py' in command[1]:
            # Exercise real file installation; reuse test dependencies instead of pip/network.
            command[1] = str(ROOT / 'scripts/install-user.py')
            command += ['--runtime-python', sys.executable]
            if '--service-only' not in command:
                plugin = self.home / 'fixture.so'
                plugin.write_bytes(b'fixture')
                command += ['--plugin', str(plugin)]
            return REAL_RUN(command, **kwargs)
        return subprocess.CompletedProcess(command, 0, stdout='', stderr='')

    def exercise(self, args=(), fail=None):
        def run(command, **kwargs):
            if fail and fail(command):
                self.commands.append(list(command))
                raise subprocess.CalledProcessError(1, command)
            return self.host_run(command, **kwargs)
        with patch.object(self.setup.subprocess, 'run', side_effect=run), \
             patch.object(self.setup, 'wait_ready'):
            return self.setup.main(list(args))

    def test_source_install_completes_defaults_and_enables_service_after_models(self):
        self.assertEqual(self.exercise(), 0)
        config = self.home / 'config/fcitx5-voice/config.toml'
        self.assertIn('backend = "streaming"', config.read_text())
        self.assertTrue((self.home / 'data/fcitx5/addon/voiceinput.conf').is_file())
        download = [c for c in self.commands if 'download-model.py' in c[1]]
        self.assertEqual(len(download), 2)
        enable = ['systemctl', '--user', 'enable', 'fcitx5-voice.service']
        restart = ['systemctl', '--user', 'restart', 'fcitx5-voice.service']
        self.assertGreater(self.commands.index(enable), self.commands.index(download[-1]))
        self.assertIn(restart, self.commands)
        self.assertIn(['im-config', '-n', 'fcitx5'], self.commands)
        self.assertIn(['fcitx5', '-rd'], self.commands)

    def test_upgrade_preserves_config_and_downloads_offline_custom_path(self):
        config = self.home / 'config/fcitx5-voice/config.toml'
        config.parent.mkdir(parents=True)
        content = 'backend = "offline"\nlanguage = "zh"\nmodel_dir = "../custom models"\n'
        config.write_text(content)
        self.assertEqual(self.exercise(), 0)
        self.assertEqual(config.read_text(), content)
        download = [c for c in self.commands if 'download-model.py' in c[1]]
        self.assertEqual(len(download), 1)
        self.assertIn('offline', download[0])
        self.assertIn(str(self.home / 'config/custom models'), download[0])

    def test_failed_download_does_not_start_service_or_change_input_method(self):
        self.assertEqual(self.exercise(fail=lambda c: 'download-model.py' in str(c)), 1)
        self.assertNotIn(['systemctl', '--user', 'restart', 'fcitx5-voice.service'], self.commands)
        self.assertFalse(any(c[0] == 'im-config' for c in self.commands))

    def test_deb_route_installs_package_without_compiling(self):
        deb = self.home / 'voice package.deb'
        deb.write_bytes(b'fixture')
        self.assertEqual(self.exercise(['--deb', str(deb)]), 0)
        self.assertTrue(any(c[:3] == ['sudo', 'apt-get', 'install'] and str(deb) in c
                            for c in self.commands))
        self.assertFalse(any(c[0] == 'cmake' for c in self.commands))
        self.assertFalse((self.home / 'data/fcitx5/addon/voiceinput.conf').exists())
        self.assertIn(['systemctl', '--user', 'start', 'fcitx5-voice-setup.service'], self.commands)
        self.assertIn(['/usr/bin/fcitx5-voice-autosetup'], self.commands)
        self.assertFalse(any('install-user.py' in str(c) for c in self.commands))

    def test_automatic_setup_launches_fcitx_outside_oneshot_cgroup(self):
        self.assertEqual(self.exercise(['--service-only', '--desktop-service']), 0)
        desktop = next(c for c in self.commands if c[0] == 'systemd-run')
        self.assertIn('--property=Type=forking', desktop)
        self.assertEqual(desktop[-2:], ['/usr/bin/fcitx5', '-rd'])
        self.assertNotIn(['fcitx5', '-rd'], self.commands)

    def test_repeated_setup_preserves_config_and_skips_disabled_punctuation(self):
        config = self.home / 'config/fcitx5-voice/config.toml'
        config.parent.mkdir(parents=True)
        content = 'punctuation = false\nthreads = 2\n'
        config.write_text(content)
        for _ in range(2):
            self.commands.clear()
            self.assertEqual(self.exercise(['--service-only']), 0)
            self.assertEqual(config.read_text(), content)
            self.assertFalse(any(c[0] in {'sudo', 'cmake'} for c in self.commands))
            download = [c for c in self.commands if 'download-model.py' in c[1]]
            self.assertEqual(len(download), 1)
            self.assertIn('--no-punctuation', download[0])

    def test_refinement_download_uses_custom_model_directory_before_start(self):
        config = self.home / 'config/fcitx5-voice/config.toml'
        config.parent.mkdir(parents=True)
        config.write_text('streaming_refine=true\nmodel_dir="../refine model"\n')
        self.assertEqual(self.exercise(['--service-only']), 0)
        commands = [c for c in self.commands if 'download-model.py' in c[1]]
        correction = next(c for c in commands if 'offline' in c)
        self.assertIn(str(self.home / 'config/refine model'), correction)
        self.assertLess(self.commands.index(correction),
                        self.commands.index(['systemctl', '--user', 'restart', 'fcitx5-voice.service']))

    def test_dependency_failure_stops_before_user_install(self):
        self.assertEqual(self.exercise(fail=lambda c: 'apt-get' in c), 1)
        self.assertFalse((self.home / '.local/bin/fcitx5-voice').exists())

    def test_service_load_failure_does_not_restart_input_method(self):
        with patch.object(self.setup.subprocess, 'run', side_effect=self.host_run), \
             patch.object(self.setup, 'wait_ready', side_effect=RuntimeError('load failed')):
            self.assertEqual(self.setup.main(['--service-only']), 1)
        self.assertNotIn(['fcitx5', '-rd'], self.commands)

    def test_invalid_existing_config_fails_before_system_changes(self):
        config = self.home / 'config/fcitx5-voice/config.toml'
        config.parent.mkdir(parents=True)
        config.write_text('language = "zh"\n')
        self.assertEqual(self.exercise(), 1)
        self.assertEqual(self.commands, [])

    def test_root_and_missing_desktop_are_rejected_before_changes(self):
        with patch.object(self.setup.os, 'getuid', return_value=0):
            self.assertEqual(self.exercise(), 1)
        with patch.dict(os.environ, DISPLAY='', WAYLAND_DISPLAY=''):
            self.assertEqual(self.exercise(), 1)
        self.assertEqual(self.commands, [])

    def test_ready_checks_protocol_without_starting_recording(self):
        path = self.home / 'run/fcitx5-voice/service.sock'
        path.parent.mkdir()
        with socket.socket(socket.AF_UNIX) as server:
            server.bind(str(path))
            server.listen()
            received = []

            def respond():
                connection, _ = server.accept()
                with connection:
                    connection.sendall(b'{"type":"ready","protocol":2}\n')
                    received.append(connection.recv(1024))

            worker = threading.Thread(target=respond, daemon=True)
            worker.start()
            self.setup.wait_ready(timeout=1)
            worker.join(2)
            self.assertEqual(received, [b''])

    def test_missing_service_times_out_instead_of_reporting_success(self):
        with self.assertRaises(RuntimeError):
            self.setup.wait_ready(timeout=0.01)


if __name__ == '__main__':
    unittest.main()
