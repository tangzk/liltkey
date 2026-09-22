import tempfile
import unittest
from pathlib import Path

from fcitx5_voice.cli import apply_overrides
from fcitx5_voice.config import Config, load_config


class ConfigTests(unittest.TestCase):
    def load(self, text, **kwargs):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.toml'
            path.write_text(text)
            return load_config(path, **kwargs)

    def test_config_controls_model_threads_and_device(self):
        config = self.load('backend="offline"\nmodel_dir="/tmp/model"\nthreads=2\n'
                           'device="alsa_input.test"\nlanguage="auto"')
        self.assertEqual(config.backend, 'offline')
        self.assertEqual(config.model_dir, Path('/tmp/model'))
        self.assertEqual(config.threads, 2)
        self.assertEqual(config.device, 'alsa_input.test')
        self.assertEqual(config.language, 'auto')

    def test_reject_unbounded_resource_settings_and_typos(self):
        for text in ['threads=0', 'threads=999', 'max_seconds=0', 'max_seconds=3600',
                     'threads=true', 'max_seconds="30"', 'language="garbage"',
                     'backend="garbage"', 'threds=2']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.load(text)

    def test_streaming_is_default_and_has_a_distinct_model_directory(self):
        config = Config()
        self.assertEqual(config.backend, 'streaming')
        self.assertEqual(config.streaming_model_dir.name,
                         'streaming-zipformer-bilingual-zh-en-2023-02-20')
        self.assertNotEqual(config.streaming_model_dir, config.model_dir)

    def test_streaming_rejects_forced_language_because_model_auto_detects(self):
        for language in ('zh', 'en', 'ja', 'ko', 'yue'):
            with self.subTest(language=language), self.assertRaisesRegex(
                    ValueError, 'streaming.*auto'):
                self.load(f'backend="streaming"\nlanguage="{language}"')

    def test_offline_retains_sensevoice_language_options(self):
        self.assertEqual(self.load('backend="offline"\nlanguage="ja"').language, 'ja')

    def test_cli_backend_override_can_select_offline_for_legacy_language_config(self):
        config = self.load('language="zh"', backend='offline')
        self.assertEqual(config.backend, 'offline')
        self.assertEqual(config.language, 'zh')

    def test_relative_model_directories_resolve_from_config_file(self):
        config = self.load('backend="offline"\nmodel_dir="legacy"\n'
                           'streaming_model_dir="online"')
        self.assertTrue(config.model_dir.is_absolute())
        self.assertEqual(config.model_dir.name, 'legacy')
        self.assertTrue(config.streaming_model_dir.is_absolute())
        self.assertEqual(config.streaming_model_dir.name, 'online')

    def test_cli_overrides_backend_and_each_model_directory(self):
        config = apply_overrides(Config(), 'offline', Path('/tmp/legacy'), Path('/tmp/live'))
        self.assertEqual(config.backend, 'offline')
        self.assertEqual(config.model_dir, Path('/tmp/legacy'))
        self.assertEqual(config.streaming_model_dir, Path('/tmp/live'))

    def test_missing_explicit_config_is_actionable_error(self):
        with self.assertRaises(FileNotFoundError):
            load_config(Path('/no-such-fcitx5-voice-config'))

    def test_punctuation_can_be_disabled_and_model_path_resolves(self):
        config = self.load('punctuation=false\npunctuation_model_dir="punct"')
        self.assertFalse(config.punctuation)
        self.assertTrue(config.punctuation_model_dir.is_absolute())
        self.assertEqual(config.punctuation_model_dir.name, 'punct')
        for value in ['"false"', '1', '[]']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.load(f'punctuation={value}')

    def test_streaming_refinement_is_explicit_and_strictly_boolean(self):
        self.assertFalse(self.load('').streaming_refine)
        self.assertTrue(self.load('streaming_refine=true').streaming_refine)
        self.assertFalse(self.load('streaming_refine=false').streaming_refine)
        for value in ['1', '"true"', '[]']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.load(f'streaming_refine={value}')
