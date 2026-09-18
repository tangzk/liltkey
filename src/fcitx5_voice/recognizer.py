"""CPU SenseVoice adapter. Only called from the service's inference worker."""

import re
import threading

from .config import Config
from .text import format_segment


def prepare_pcm(pcm):
    import numpy as np
    if len(pcm) < 3200 or len(pcm) % 2:
        raise ValueError('需要至少 0.1 秒的 16 kHz 单声道 PCM16 音频')
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
        import numpy as np
        samples = prepare_pcm(pcm)
        text = ''
        with self.lock:
            # Keep inference chunks bounded even when a hold exceeds 30 seconds.
            for offset in range(0, len(samples), 30 * 16000):
                chunk = samples[offset:offset + 30 * 16000]
                if float(np.max(np.abs(chunk))) < 0.001:
                    continue
                if len(chunk) < 1600:
                    chunk = np.pad(chunk, (0, 1600 - len(chunk)))
                stream = self.model.create_stream()
                stream.accept_waveform(16000, chunk)
                self.model.decode_stream(stream)
                segment = re.sub(r'<\|[^|]*\|>', '', stream.result.text).strip()
                text += format_segment(segment, text[-1:])
                if len(text.encode('utf-8')) > 8192:
                    raise ValueError('识别结果过长，请分成短句输入')
        return text
