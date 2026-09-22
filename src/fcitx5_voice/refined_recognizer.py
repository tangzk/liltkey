"""Streaming drafts with bounded, audio-based correction before each commit."""

import logging

from .recognizer import prepare_pcm
from .text import finalize_text


class RefinedStreamingRecognizer:
    def __init__(self, preview, correct, fallback_finalize=None):
        self.preview = preview
        self.correct = correct
        self.fallback_finalize = fallback_finalize or finalize_text

    def create_decoder(self):
        return RefinedStreamingDecoder(
            self.preview.create_decoder, self.correct, self.fallback_finalize)


class RefinedStreamingDecoder:
    # PCM16 mono at 16 kHz: at most 20 seconds (640 KB) retained per segment.
    MAX_BYTES = 20 * 16000 * 2
    BLOCK_BYTES = 3200

    def __init__(self, create_preview, correct, fallback_finalize):
        self.create_preview = create_preview
        self.correct = correct
        self.fallback_finalize = fallback_finalize
        self.preview = create_preview()
        self.pcm = bytearray()
        self.draft = ''
        self.finished = False
        self.refining = True

    def accept(self, pcm):
        if self.finished:
            raise RuntimeError('finish 之后不能继续输入音频')
        if len(pcm) % 2:
            raise ValueError('音频必须是完整的 PCM16 样本')
        events = []
        for offset in range(0, len(pcm), self.BLOCK_BYTES):
            block = pcm[offset:offset + self.BLOCK_BYTES]
            # A preceding short block can leave less than BLOCK_BYTES capacity.
            remaining = self.MAX_BYTES - len(self.pcm)
            for part in (block[:remaining], block[remaining:]):
                if not part:
                    continue
                if not self.refining:
                    events.extend(self._fallback_events(self.preview.accept(part)))
                    continue
                self.pcm.extend(part)
                endpoint = False
                pending = self.preview.accept(part)
                for index, (kind, text) in enumerate(pending):
                    self.draft = text
                    if kind == 'final':
                        endpoint = True
                        break
                    events.append((kind, text))
                if endpoint or len(self.pcm) == self.MAX_BYTES:
                    if not endpoint:
                        self._drain_preview()
                    events.append(('final', self._correct()))
                    if endpoint and not self.refining:
                        # A failed correction did not transcribe the lookahead.
                        # Keep the native stream and its remaining events; use
                        # plain streaming for the rest of this session.
                        events.extend(self._fallback_events(pending[index + 1:]))
                        continue
                    # Endpoint timestamps describe decoded frames, not all the
                    # accepted PCM (the model has lookahead). Correction covers
                    # the ENTIRE accepted block. Start a new native stream at
                    # that same boundary, discarding its already-covered lookahead.
                    self.preview = self.create_preview()
                    self.draft = ''
        return events

    def finish(self):
        if self.finished:
            return []
        self.finished = True
        if not self.refining:
            return self._fallback_events(self.preview.finish())
        if not self.pcm:
            return []
        self._drain_preview()
        return [('final', self._correct())]

    def _drain_preview(self):
        for _, text in self.preview.finish():
            self.draft = text

    def _fallback_events(self, events):
        return [(kind, self.fallback_finalize(text) if kind == 'final' else text)
                for kind, text in events]

    def _correct(self):
        pcm = bytes(self.pcm)
        self.pcm.clear()
        try:
            # This is only a minimum length / digital-silence guard, not VAD.
            prepare_pcm(pcm)
        except ValueError:
            return self.fallback_finalize(self.draft)
        try:
            text = self.correct(pcm)
            if not isinstance(text, str) or not text.strip():
                raise ValueError('空校正结果')
            # SenseVoice already supplies punctuation. Do not apply CT twice.
            text = finalize_text(text)
            if not text:
                raise ValueError('空校正结果')
            return text
        except Exception:
            self.refining = False
            # Neither transcripts nor native exception text belong in logs.
            logging.getLogger(__name__).warning('语音校正失败，本次录音继续使用流式识别')
            return self.fallback_finalize(self.draft)
