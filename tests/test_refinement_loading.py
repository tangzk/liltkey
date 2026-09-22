import unittest
from unittest.mock import patch

from fcitx5_voice.config import Config
from test_refined_recognizer import Preview, BLOCK


class RefinementLoadingTests(unittest.TestCase):
    def test_enabled_pipeline_corrects_audio_and_avoids_duplicate_punctuation(self):
        from fcitx5_voice.cli import build_streaming
        with patch('fcitx5_voice.streaming_recognizer.StreamingRecognizer', return_value=Preview()), \
             patch('fcitx5_voice.recognizer.SenseVoiceRecognizer', return_value=lambda pcm: '你好。'), \
             patch('fcitx5_voice.cli.build_finalizer', return_value=lambda text: text + '！'):
            model, finalize = build_streaming(Config(streaming_refine=True))
            decoder = model.create_decoder()
            decoder.accept(BLOCK)
            self.assertEqual([finalize(text) for _, text in decoder.finish()], ['你好。'])

    def test_disabled_pipeline_never_loads_correction_weights(self):
        from fcitx5_voice.cli import build_streaming
        with patch('fcitx5_voice.streaming_recognizer.StreamingRecognizer', return_value=Preview()), \
             patch('fcitx5_voice.recognizer.SenseVoiceRecognizer', side_effect=AssertionError('disabled')), \
             patch('fcitx5_voice.cli.build_finalizer', return_value=lambda text: text + '！'):
            model, finalize = build_streaming(Config(streaming_refine=False))
            decoder = model.create_decoder()
            self.assertEqual([finalize(text) for _, text in decoder.finish()], ['松键草稿！'])

    def test_missing_optional_weights_preserve_streaming_operation(self):
        from fcitx5_voice.cli import build_streaming
        with patch('fcitx5_voice.streaming_recognizer.StreamingRecognizer', return_value=Preview()), \
             patch('fcitx5_voice.recognizer.SenseVoiceRecognizer', side_effect=FileNotFoundError('missing')), \
             patch('fcitx5_voice.cli.build_finalizer', return_value=lambda text: text + '！'), \
             self.assertLogs('fcitx5_voice.cli', level='WARNING'):
            model, finalize = build_streaming(Config(streaming_refine=True))
            decoder = model.create_decoder()
            self.assertEqual([finalize(text) for _, text in decoder.finish()], ['松键草稿！'])
