import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fcitx5_voice.punctuation import PunctuationRestorer


class FakeModelConfig:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class FakePunctuationConfig:
    def __init__(self, model):
        self.model = model


class FakePunctuation:
    result = '你好，world。'
    loads = 0
    active = 0
    max_active = 0
    calls = 0
    state_lock = threading.Lock()

    def __init__(self, config):
        type(self).loads += 1
        self.config = config

    def add_punctuation(self, text):
        with type(self).state_lock:
            type(self).calls += 1
            type(self).active += 1
            type(self).max_active = max(type(self).max_active, type(self).active)
        time.sleep(0.01)
        with type(self).state_lock:
            type(self).active -= 1
        return type(self).result if callable(type(self).result) is False else type(self).result(text)


def fake_sherpa():
    return SimpleNamespace(
        OfflinePunctuationModelConfig=FakeModelConfig,
        OfflinePunctuationConfig=FakePunctuationConfig,
        OfflinePunctuation=FakePunctuation,
    )


class PunctuationRestorerTests(unittest.TestCase):
    def setUp(self):
        FakePunctuation.result = '你好，world。'
        FakePunctuation.loads = 0
        FakePunctuation.active = 0
        FakePunctuation.max_active = 0
        FakePunctuation.calls = 0

    def config(self, directory, threads=3):
        return SimpleNamespace(punctuation_model_dir=Path(directory), threads=threads)

    def ready_model(self, root):
        model = Path(root) / 'model.int8.onnx'
        model.write_bytes(b'weights')
        return model

    def make_restorer(self, root, threads=3):
        model = self.ready_model(root)
        with patch.dict(sys.modules, {'sherpa_onnx': fake_sherpa()}):
            restorer = PunctuationRestorer(self.config(root, threads))
        return restorer, model

    def test_missing_model_names_path_and_download_command(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(FileNotFoundError, r'model\.int8\.onnx.*download-model'):
                PunctuationRestorer(self.config(directory))

    def test_configures_quantized_ct_transformer_for_cpu(self):
        with tempfile.TemporaryDirectory() as directory:
            restorer, model = self.make_restorer(directory, threads=3)

            configured = restorer.model.config.model
            self.assertEqual(configured.ct_transformer, str(model))
            self.assertEqual(configured.num_threads, 3)
            self.assertEqual(configured.provider, 'cpu')

    def test_returns_model_punctuation_when_spoken_content_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            restorer, _ = self.make_restorer(directory)

            self.assertEqual(restorer('你好 world'), '你好，world。')

    def test_empty_input_skips_inference(self):
        with tempfile.TemporaryDirectory() as directory:
            restorer, _ = self.make_restorer(directory)

            self.assertEqual(restorer(''), '')
            self.assertEqual(restorer('   '), '   ')
            self.assertEqual(FakePunctuation.calls, 0)

    def test_rejects_input_and_output_over_8192_utf8_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            restorer, _ = self.make_restorer(directory)

            FakePunctuation.result = lambda text: text
            self.assertEqual(restorer('x' * 8192), 'x' * 8192)
            with self.assertRaisesRegex(ValueError, '过长'):
                restorer('x' * 8193)
            FakePunctuation.result = lambda text: text + '，' * 4096
            with self.assertRaisesRegex(ValueError, '过长'):
                restorer('kept')

    def test_rejects_output_that_changes_spoken_content(self):
        with tempfile.TemporaryDirectory() as directory:
            restorer, _ = self.make_restorer(directory)
            FakePunctuation.result = 'different。'

            with self.assertRaisesRegex(ValueError, '改变'):
                restorer('original')

    def test_rejects_removal_of_existing_meaningful_punctuation(self):
        cases = (
            ('3.14', '314。'),
            ("can't", 'cant。'),
            ('https://example.test/path?q=1', 'httpsexample.test/pathq=1。'),
        )
        for original, changed in cases:
            with self.subTest(original=original), tempfile.TemporaryDirectory() as directory:
                restorer, _ = self.make_restorer(directory)
                FakePunctuation.result = changed

                with self.assertRaisesRegex(ValueError, '改变'):
                    restorer(original)

    def test_rejects_collapsed_english_word_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            restorer, _ = self.make_restorer(directory)
            FakePunctuation.result = 'helloworld。'

            with self.assertRaisesRegex(ValueError, '改变'):
                restorer('hello world')

    def test_rejects_insertions_inside_structured_ascii_spans(self):
        cases = (
            ('3.14', '3 . 14。'),
            ('1,000.25', '1 , 000 . 25。'),
            ("can't", "can ' t。"),
            ('https://example.test/path?q=1',
             'https。: / / example . test / path ? q = 1。'),
            ('www.example.test', 'www . example . test。'),
            ('3.14 3.14', '3.14 3. 14。'),
            ("can't can't", "can't can 't。"),
        )
        for original, changed in cases:
            with self.subTest(original=original), tempfile.TemporaryDirectory() as directory:
                restorer, _ = self.make_restorer(directory)
                FakePunctuation.result = changed

                with self.assertRaisesRegex(ValueError, '改变'):
                    restorer(original)

    def test_allows_inserted_punctuation_at_english_boundary_and_removed_cjk_space(self):
        cases = (
            ('hello world', 'hello，world。'),
            ('你 好', '你好。'),
        )
        for original, punctuated in cases:
            with self.subTest(original=original), tempfile.TemporaryDirectory() as directory:
                restorer, _ = self.make_restorer(directory)
                FakePunctuation.result = punctuated

                self.assertEqual(restorer(original), punctuated)

    def test_one_model_instance_serializes_concurrent_inference(self):
        with tempfile.TemporaryDirectory() as directory:
            restorer, _ = self.make_restorer(directory)
            FakePunctuation.result = lambda text: text + '。'
            outputs = []
            threads = [threading.Thread(target=lambda text=text: outputs.append(restorer(text)))
                       for text in ('一', '二', '三', '四')]

            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertCountEqual(outputs, ['一。', '二。', '三。', '四。'])
            self.assertEqual(FakePunctuation.loads, 1)
            self.assertEqual(FakePunctuation.max_active, 1)


if __name__ == '__main__':
    unittest.main()
