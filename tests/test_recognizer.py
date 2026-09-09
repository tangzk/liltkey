import unittest
import tempfile
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
