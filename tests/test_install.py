import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import shutil
import configparser

ROOT = Path(__file__).resolve().parents[1]


class InstallTests(unittest.TestCase):
    def test_user_install_preserves_existing_config_and_uninstalls_only_owned_files(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            env = dict(os.environ, HOME=str(home), XDG_DATA_HOME=str(home/'data'),
                       XDG_CONFIG_HOME=str(home/'config'))
            addon = home / 'dummy.so'
            addon.write_bytes(b'fake-library-for-install-path-test')
            existing = home/'config/fcitx5-voice/config.toml'
            existing.parent.mkdir(parents=True)
            existing.write_text('threads = 2\n')
            command = [sys.executable, str(ROOT/'scripts/install-user.py'),
                       '--plugin', str(addon), '--runtime-python', sys.executable]
            result = subprocess.run(command, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(existing.read_text(), 'threads = 2\n')
            conf = home/'data/fcitx5/addon/voiceinput.conf'
            self.assertTrue(conf.is_file())
            self.assertTrue((home/'.local/lib/fcitx5-voice/voiceinput.so').is_file())
            wrapper = home/'.local/bin/fcitx5-voice'
            help_result = subprocess.run([str(wrapper), '--help'], env=env, capture_output=True)
            self.assertEqual(help_result.returncode, 0, help_result.stderr)
            # Migrating to the packaged native addon must remove our old user override.
            migrated = subprocess.run(command + ['--service-only'], env=env, capture_output=True, text=True)
            self.assertEqual(migrated.returncode, 0, migrated.stderr)
            self.assertFalse(conf.exists())
            self.assertFalse((home/'.local/lib/fcitx5-voice/voiceinput.so').exists())
            result = subprocess.run([sys.executable, str(ROOT/'scripts/install-user.py'), '--uninstall'],
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(conf.exists())
            self.assertFalse(wrapper.exists())
            self.assertTrue(existing.exists())
            self.assertTrue(Path(sys.executable).exists())

    @unittest.skipUnless(shutil.which('dpkg-deb'), 'Debian packaging tool unavailable')
    def test_deb_contains_portable_addon_and_service_setup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin = root/'test.so'
            plugin.write_bytes(b'package-fixture')
            result = subprocess.run([sys.executable, str(ROOT/'scripts/build-deb.py'),
                                     '--plugin', str(plugin), '--output', str(root/'dist')],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            deb = next((root/'dist').glob('*.deb'))
            stage = root/'stage'
            subprocess.run(['dpkg-deb', '-x', str(deb), str(stage)], check=True)
            addon = configparser.ConfigParser()
            addon.read(stage/'usr/share/fcitx5/addon/voiceinput.conf')
            self.assertEqual(addon['Addon']['Library'], 'voiceinput')
            self.assertEqual(addon['Addon']['Version'], '0.1.0')
            self.assertTrue((stage/'usr/share/fcitx5-voice/src/fcitx5_voice/server.py').is_file())
            self.assertTrue((stage/'usr/bin/fcitx5-voice-setup').stat().st_mode & 0o111)
            self.assertEqual(len(list((stage/'usr/lib').glob('*/fcitx5/voiceinput.so'))), 1)
