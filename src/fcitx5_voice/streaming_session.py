"""Live dictation lifecycle; only this session stamps protocol sequence numbers."""

import asyncio

from .session import Session
from .text import format_segment


class StreamingSession(Session):
    def __init__(self, capture_factory, recognize, emit, max_seconds=30, finalize=None):
        super().__init__(capture_factory, recognize, emit, max_seconds)
        self.finalize = finalize

    async def start(self, session_id, continuous=False):
        await super().start(session_id, continuous=continuous)
        if (not self.closed and self.id == session_id and self.phase == 'recording'
                and (self.worker is None or self.worker.done())):
            self.worker = asyncio.create_task(self._run(session_id, self.capture))

    async def stop(self, session_id):
        async with self.lock:
            if self.closed:
                return
            if session_id == self.id and self.phase == 'transcribing':
                return
            if session_id != self.id or self.phase != 'recording':
                await self.error(session_id, '没有对应的录音会话')
                return
            self._clear_timer()
            self.phase = 'transcribing'
            try:
                # This seals the queue; the worker still consumes every captured chunk.
                await self.capture.stop()
                await self.emit({'type': 'transcribing', 'id': session_id})
            except (ConnectionError, asyncio.TimeoutError):
                self.closed = True
                await self.capture.cancel()
                self.capture = None
                self.id, self.phase = None, 'idle'
            except Exception as exc:
                await self.capture.cancel()
                self.capture = None
                self.id, self.phase = None, 'idle'
                await self.error(session_id, f'音频采集失败：{exc}')

    def _active(self, session_id):
        return not self.closed and self.id == session_id and self.phase in {'recording', 'transcribing'}

    async def _run(self, session_id, capture):
        segment, seq, previous = 1, 0, None
        committed_tail = ''

        async def publish(results):
            nonlocal segment, seq, previous, committed_tail
            for kind, text in results:
                if kind not in {'partial', 'final'} or not isinstance(text, str):
                    raise ValueError('无效的流式识别结果')
                if not self._active(session_id):
                    return
                if kind == 'final' and text.strip() and self.finalize is not None:
                    text = await asyncio.to_thread(self.finalize, text)
                text = format_segment(text, committed_tail, mixed_spacing=self.finalize is not None)
                async with self.lock:
                    if not self._active(session_id):
                        return
                    if kind == 'partial' and text == previous:
                        continue
                    seq += 1
                    await self.emit({'type': kind, 'id': session_id, 'segment': segment,
                                     'seq': seq, 'text': text})
                    previous = text
                    if kind == 'final':
                        if text:
                            committed_tail = text[-1]
                        segment += 1
                        previous = None

        try:
            decoder = await asyncio.to_thread(self.recognize.create_decoder)
            async for pcm in capture.chunks():
                if not self._active(session_id):
                    return
                await publish(await asyncio.to_thread(decoder.accept, pcm))
            if not self._active(session_id):
                return
            if self.phase != 'transcribing':
                raise RuntimeError('麦克风采集中断，请检查设备后重试')
            await publish(await asyncio.to_thread(decoder.finish))
            async with self.lock:
                if self._active(session_id):
                    self._clear_timer()
                    await self.emit({'type': 'finished', 'id': session_id})
                    self.capture = None
                    self.id, self.phase = None, 'idle'
        except (ConnectionError, asyncio.TimeoutError):
            async with self.lock:
                if self.id == session_id:
                    self.closed = True
                    self._clear_timer()
                    await capture.cancel()
                    self.capture = None
                    self.id, self.phase = None, 'idle'
        except Exception as exc:
            async with self.lock:
                if self._active(session_id):
                    self._clear_timer()
                    await capture.cancel()
                    self.capture = None
                    self.id, self.phase = None, 'idle'
                    try:
                        await self.error(session_id, f'流式识别失败：{exc}')
                    except (ConnectionError, asyncio.TimeoutError):
                        self.closed = True
