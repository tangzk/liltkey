import unittest
from unittest.mock import patch

from fcitx5_voice.cli import build_finalizer
from fcitx5_voice.config import Config


class FinalizerTests(unittest.TestCase):
    def test_disabled_punctuation_does_not_load_model_but_formats_spaces(self):
        from pathlib import Path
        processor = build_finalizer(Config(punctuation=False, punctuation_model_dir=Path('/not-a-model')))
        self.assertEqual(processor('使用Linux系统'), '使用 Linux 系统')

    def test_enabled_model_loaded_once_and_shared_across_finals(self):
        with patch('fcitx5_voice.punctuation.PunctuationRestorer') as constructor:
            constructor.return_value.side_effect = ['你好，世界。', '明天见！']
            processor = build_finalizer(Config())
            self.assertEqual(processor('你好世界'), '你好，世界。')
            self.assertEqual(processor('明天见'), '明天见！')
            self.assertEqual(constructor.call_count, 1)
