import contextlib
import io
import json
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

import numpy as np

from fcitx5_voice.config import Config


class FakeStream:
    def __init__(self):
        self.accepted = []
        self.finished = False

    def accept_waveform(self, sample_rate, samples):
        self.accepted.append((sample_rate, samples.copy()))

    def input_finished(self):
        self.finished = True


class FakeOnlineRecognizer:
    def __init__(self):
        self.stream = FakeStream()
        self.results = []
        self.current_text = ''
        self.current_endpoint = False
        self.resets = 0

    def create_stream(self):
        return self.stream

    def queue(self, *results):
        self.results.extend(results)

    def is_ready(self, stream):
        return bool(self.results)

    def decode_stream(self, stream):
        self.current_text, self.current_endpoint = self.results.pop(0)

    def get_result(self, stream):
        return self.current_text

    def is_endpoint(self, stream):
        return self.current_endpoint

    def reset(self, stream):
        self.resets += 1
        self.current_text = ''
        self.current_endpoint = False


class StreamingRecognizerTests(unittest.TestCase):
    def decoder(self):
        from fcitx5_voice.streaming_recognizer import StreamingRecognizer
        model = FakeOnlineRecognizer()
        recognizer = StreamingRecognizer.__new__(StreamingRecognizer)
        recognizer.model = model
        return model, recognizer.create_decoder()

    def test_accept_emits_full_revisions_and_one_endpoint_final(self):
        model, decoder = self.decoder()
        model.queue(('明', False), ('明天', False), ('明天下午', True))

        events = decoder.accept((np.arange(320, dtype='<i2')).tobytes())

        self.assertEqual(events, [('partial', '明'), ('partial', '明天'),
                                  ('final', '明天下午')])
        self.assertEqual(model.resets, 1)
        self.assertEqual(decoder.accept(b'\x00\x00' * 320), [])

    def test_finish_adds_tail_then_flushes_without_duplicate_endpoint_final(self):
        model, decoder = self.decoder()
        model.queue(('hello', False))
        self.assertEqual(decoder.accept(b'\x00\x01' * 320), [('partial', 'hello')])
        model.queue(('hello world', True))

        events = decoder.finish()

        self.assertEqual(events, [('final', 'hello world')])
        self.assertTrue(model.stream.finished)
        self.assertEqual(model.stream.accepted[-1][0], 16000)
        self.assertEqual(len(model.stream.accepted[-1][1]), 8000)
        self.assertTrue(np.all(model.stream.accepted[-1][1] == 0))
        self.assertEqual(decoder.finish(), [])

    def test_finish_drains_past_endpoint_and_emits_only_latest_final(self):
        model, decoder = self.decoder()
        model.queue(('draft', False))
        self.assertEqual(decoder.accept(b'\x00\x01' * 320), [('partial', 'draft')])
        model.queue(('stale endpoint', True), ('fully drained final', False))

        self.assertEqual(decoder.finish(), [('final', 'fully drained final')])

    def test_rejects_unbounded_result_before_returning_it(self):
        model, decoder = self.decoder()
        model.queue(('x' * 8193, False))
        with self.assertRaisesRegex(ValueError, '过长'):
            decoder.accept(b'\x00\x01' * 320)

    def test_empty_final_clears_a_revised_away_partial(self):
        model, decoder = self.decoder()
        model.queue(('noise', False))
        self.assertEqual(decoder.accept(b'\x01\x00' * 320), [('partial', 'noise')])
        model.queue(('', True))
        self.assertEqual(decoder.finish(), [('final', '')])

    def test_rejects_odd_pcm_and_audio_after_finish(self):
        _, decoder = self.decoder()
        with self.assertRaisesRegex(ValueError, 'PCM16'):
            decoder.accept(b'\x00')
        decoder.finish()
        with self.assertRaisesRegex(RuntimeError, 'finish'):
            decoder.accept(b'\x00\x00')

    def test_constructor_loads_cpu_endpoint_transducer_once(self):
        from fcitx5_voice.streaming_recognizer import StreamingRecognizer

        class Factory:
            calls = []

            @classmethod
            def from_transducer(cls, **kwargs):
                cls.calls.append(kwargs)
                return FakeOnlineRecognizer()

        fake_module = type('Sherpa', (), {'OnlineRecognizer': Factory})
        with tempfile.TemporaryDirectory() as directory:
            model_dir = Path(directory)
            for name in ('encoder-epoch-99-avg-1.int8.onnx',
                         'decoder-epoch-99-avg-1.onnx',
                         'joiner-epoch-99-avg-1.int8.onnx', 'tokens.txt'):
                (model_dir / name).touch()
            with patch.dict('sys.modules', {'sherpa_onnx': fake_module}):
                recognizer = StreamingRecognizer(Config(streaming_model_dir=model_dir, threads=3))
                recognizer.create_decoder()
                recognizer.create_decoder()

        self.assertEqual(len(Factory.calls), 1)
        options = Factory.calls[0]
        self.assertEqual(options['provider'], 'cpu')
        self.assertEqual(options['num_threads'], 3)
        self.assertTrue(options['enable_endpoint_detection'])
        self.assertEqual(options['rule3_min_utterance_length'], 20.0)
        self.assertTrue(options['encoder'].endswith('encoder-epoch-99-avg-1.int8.onnx'))

    def test_missing_streaming_model_has_download_instruction(self):
        from fcitx5_voice.streaming_recognizer import StreamingRecognizer
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(FileNotFoundError, 'download-model'):
                StreamingRecognizer(Config(streaming_model_dir=Path(directory)))

    def test_cli_transcribe_preserves_english_boundaries_and_cjk_adjacency(self):
        from fcitx5_voice.cli import transcribe

        class Decoder:
            emitted = False

            def accept(self, pcm):
                if self.emitted:
                    return []
                self.emitted = True
                return [('final', 'hello'), ('final', 'world'),
                        ('final', '中文'), ('final', '继续')]

            def finish(self):
                return []

        class Recognizer:
            def __init__(self, config):
                pass

            def create_decoder(self):
                return Decoder()

        with tempfile.TemporaryDirectory() as directory:
            wav_path = Path(directory) / 'fixture.wav'
            with wave.open(str(wav_path), 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(b'\x00\x00' * 1600)
            output = io.StringIO()
            with patch('fcitx5_voice.streaming_recognizer.StreamingRecognizer', Recognizer), \
                    contextlib.redirect_stdout(output):
                self.assertEqual(transcribe(Config(punctuation=False, streaming_refine=False), wav_path, 1), 0)

        self.assertEqual(json.loads(output.getvalue())['text'], 'hello world 中文继续')
