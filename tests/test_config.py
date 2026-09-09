import tempfile
import unittest
from pathlib import Path

from fcitx5_voice.config import load_config


class ConfigTests(unittest.TestCase):
    def load(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.toml'
            path.write_text(text)
            return load_config(path)

    def test_config_controls_model_threads_and_device(self):
        config = self.load('model_dir="/tmp/model"\nthreads=2\ndevice="alsa_input.test"\nlanguage="auto"')
        self.assertEqual(config.model_dir, Path('/tmp/model'))
        self.assertEqual(config.threads, 2)
        self.assertEqual(config.device, 'alsa_input.test')
        self.assertEqual(config.language, 'auto')

    def test_reject_unbounded_resource_settings_and_typos(self):
        for text in ['threads=0', 'threads=999', 'max_seconds=0', 'max_seconds=3600',
                     'threads=true', 'max_seconds="30"', 'language="garbage"', 'threds=2']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.load(text)

    def test_missing_explicit_config_is_actionable_error(self):
        with self.assertRaises(FileNotFoundError):
            load_config(Path('/no-such-fcitx5-voice-config'))
