"""Persistent per-session online decoding for the bilingual Zipformer model."""

import numpy as np

from .config import Config


ENCODER = 'encoder-epoch-99-avg-1.int8.onnx'
DECODER = 'decoder-epoch-99-avg-1.onnx'
JOINER = 'joiner-epoch-99-avg-1.int8.onnx'
TOKENS = 'tokens.txt'


class StreamingRecognizer:
    """Load immutable weights once and create one decoder per voice session."""

    def __init__(self, config: Config):
        paths = {name: config.streaming_model_dir / name
                 for name in (ENCODER, DECODER, JOINER, TOKENS)}
        missing = [path.name for path in paths.values() if not path.is_file()]
        if missing:
            raise FileNotFoundError(
                f'流式模型未就绪：{config.streaming_model_dir}（缺少 {", ".join(missing)}）。'
                '请运行 scripts/download-model.py。')
        import sherpa_onnx
        self.model = sherpa_onnx.OnlineRecognizer.from_transducer(
            tokens=str(paths[TOKENS]), encoder=str(paths[ENCODER]),
            decoder=str(paths[DECODER]), joiner=str(paths[JOINER]),
            num_threads=config.threads, sample_rate=16000, provider='cpu',
            decoding_method='greedy_search', enable_endpoint_detection=True,
            rule1_min_trailing_silence=2.4,
            rule2_min_trailing_silence=1.2,
            rule3_min_utterance_length=20.0)

    def create_decoder(self):
        return StreamingDecoder(self.model)


class StreamingDecoder:
    """Stateful decoder; all methods must run on the session inference worker."""

    def __init__(self, model):
        self.model = model
        self.stream = model.create_stream()
        self.last_text = ''
        self.segment_active = False
        self.finished = False

    def accept(self, pcm: bytes):
        if self.finished:
            raise RuntimeError('finish 之后不能继续输入音频')
        if len(pcm) % 2:
            raise ValueError('音频必须是完整的 PCM16 样本')
        if not pcm:
            return []
        samples = np.frombuffer(pcm, dtype='<i2').astype(np.float32) / 32768.0
        self.stream.accept_waveform(16000, samples)
        return self._decode()

    def finish(self):
        if self.finished:
            return []
        self.finished = True
        self.stream.accept_waveform(16000, np.zeros(8000, dtype=np.float32))
        self.stream.input_finished()
        text = self._result()
        while self.model.is_ready(self.stream):
            self.model.decode_stream(self.stream)
            text = self._result()
        if self.segment_active or text:
            self.last_text = ''
            self.segment_active = False
            return [('final', text)]
        return []

    def _result(self):
        result = self.model.get_result(self.stream)
        text = result if isinstance(result, str) else result.text
        if len(text.encode('utf-8')) > 8192:
            raise ValueError('单句识别结果过长，请分成短句输入')
        return text

    def _decode(self):
        events = []
        while self.model.is_ready(self.stream):
            self.model.decode_stream(self.stream)
            text = self._result()
            endpoint = self.model.is_endpoint(self.stream)
            if endpoint:
                if self.segment_active or text:
                    events.append(('final', text))
                self.last_text = ''
                self.segment_active = False
                self.model.reset(self.stream)
                continue
            if text != self.last_text:
                events.append(('partial', text))
                self.last_text = text
                self.segment_active = True
        return events
