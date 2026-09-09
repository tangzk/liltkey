"""CPU SenseVoice adapter. Only called from the service's inference worker."""

import re
import threading

from .config import Config


def prepare_pcm(pcm):
    import numpy as np
    if len(pcm) < 3200 or len(pcm) % 2 or len(pcm) > 30 * 32000:
        raise ValueError('需要 0.1～30 秒的 16 kHz 单声道 PCM16 音频')
    samples = np.frombuffer(pcm, dtype='<i2').astype(np.float32) / 32768.0
    # Reject digital silence; this is deliberately not advertised as neural VAD.
    if float(np.max(np.abs(samples))) < 0.001:
        raise ValueError('音频无声或音量过低，请检查麦克风')
    return samples


class SenseVoiceRecognizer:
    def __init__(self, config: Config):
        model = config.model_dir / 'model.int8.onnx'
        tokens = config.model_dir / 'tokens.txt'
        if not model.is_file() or not tokens.is_file():
            raise FileNotFoundError(f'模型未就绪：{config.model_dir}。请运行 scripts/download-model.py。')
        import sherpa_onnx
        self.model = sherpa_onnx.OfflineRecognizer.from_sense_voice(
            model=str(model), tokens=str(tokens), num_threads=config.threads,
            sample_rate=16000, provider='cpu',
            language='' if config.language == 'auto' else config.language, use_itn=True)
        self.lock = threading.Lock()

    def __call__(self, pcm):
        samples = prepare_pcm(pcm)
        with self.lock:
            stream = self.model.create_stream()
            stream.accept_waveform(16000, samples)
            self.model.decode_stream(stream)
            return re.sub(r'<\|[^|]*\|>', '', stream.result.text).strip()
