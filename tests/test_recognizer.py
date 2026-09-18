import unittest
import tempfile
import threading
from types import SimpleNamespace
from pathlib import Path
from fcitx5_voice.config import Config
from fcitx5_voice.recognizer import SenseVoiceRecognizer, prepare_pcm


class RecognizerTests(unittest.TestCase):
    def test_missing_model_has_download_instruction(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(FileNotFoundError, 'download-model'):
                SenseVoiceRecognizer(Config(model_dir=Path(directory)))

    def test_silence_and_truncated_pcm_are_rejected(self):
        for pcm in [b'', b'\x00' * 16000, b'\x00\x01\x02']:
            with self.subTest(length=len(pcm)), self.assertRaises(ValueError):
                prepare_pcm(pcm)

    def test_pcm_is_little_endian_normalized_and_keeps_edges(self):
        import numpy as np
        samples = np.array([32767, -32768, 16384, -16384] * 1600, dtype='<i2')
        result = prepare_pcm(samples.tobytes())
        self.assertEqual(result.dtype, np.float32)
        self.assertAlmostEqual(float(result[1]), -1.0)
        self.assertAlmostEqual(float(result[-1]), -0.5)


class LongOfflineRecordingTests(unittest.TestCase):
    def recognizer(self):
        accepted = []
        class Model:
            def create_stream(self):
                class Stream:
                    result = SimpleNamespace(text='')
                    def accept_waveform(self, rate, samples):
                        accepted.append(samples.copy())
                return Stream()
            def decode_stream(self, stream):
                stream.result.text = 'hello' if len(accepted) == 1 else 'world'
        recognizer = SenseVoiceRecognizer.__new__(SenseVoiceRecognizer)
        recognizer.model = Model()
        recognizer.lock = threading.Lock()
        return recognizer, accepted

    def test_long_recording_is_decoded_in_bounded_chunks_without_losing_tail(self):
        recognize, accepted = self.recognizer()
        self.assertEqual(recognize(b'\x00\x20' * (31 * 16000)), 'hello world')
        self.assertEqual([len(samples) for samples in accepted], [480000, 16000])
        self.assertTrue(all((samples == 0.25).all() for samples in accepted))

    def test_silent_chunk_does_not_discard_following_speech(self):
        recognize, accepted = self.recognizer()
        self.assertEqual(recognize(b'\x00\x00' * 480000 + b'\x00\x20' * 16000), 'hello')
        self.assertEqual([len(samples) for samples in accepted], [16000])

    def test_short_tail_is_padded_instead_of_lost(self):
        recognize, accepted = self.recognizer()
        self.assertEqual(recognize(b'\x00\x20' * 480001), 'hello world')
        self.assertEqual([len(samples) for samples in accepted], [480000, 1600])
        self.assertEqual(accepted[-1][0], 0.25)
        self.assertTrue((accepted[-1][1:] == 0).all())
