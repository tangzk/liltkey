"""One microphone owner, bounded inference and cancellation-safe result delivery."""

import asyncio


class Session:
    def __init__(self, capture_factory, recognize, emit, max_seconds=30):
        self.capture_factory = capture_factory
        self.recognize = recognize
        self.emit = emit
        self.max_seconds = max_seconds
        self.capture = None
        self.id = None
        self.phase = 'idle'
        self.closed = False
        self.worker = None
        self.timer = None
        self.lock = asyncio.Lock()

    async def error(self, session_id, message):
        event = {'type': 'error', 'message': message}
        if isinstance(session_id, str) and len(session_id.encode('utf-8')) <= 128:
            event['id'] = session_id
        if not self.closed:
            await self.emit(event)

    async def start(self, session_id):
        async with self.lock:
            if self.closed:
                return
            if (not isinstance(session_id, str) or not session_id
                    or len(session_id.encode('utf-8')) > 128
                    or any(ord(c) < 32 for c in session_id)):
                await self.error(None, '无效的会话标识')
                return
            if self.phase != 'idle' or (self.worker and not self.worker.done()):
                await self.error(session_id, '上一段语音仍在处理，请稍后重试')
                return
            self.capture = self.capture_factory()
            self.id = session_id
            try:
                await self.capture.start()
            except Exception as exc:
                await self.capture.cancel()
                self.capture = None
                self.id = None
                await self.error(session_id, f'麦克风启动失败：{exc}')
                return
            self.phase = 'recording'
            self.timer = asyncio.create_task(self._limit(session_id))
            await self.emit({'type': 'recording', 'id': session_id})

    async def _limit(self, session_id):
        await asyncio.sleep(self.max_seconds)
        await self.stop(session_id)

    def _clear_timer(self):
        if self.timer and self.timer is not asyncio.current_task():
            self.timer.cancel()
        self.timer = None

    async def stop(self, session_id):
        async with self.lock:
            if self.closed:
                return
            if session_id == self.id and self.phase == 'transcribing':
                # The duration timer and release hotkey may end the same recording.
                return
            if session_id != self.id or self.phase != 'recording':
                await self.error(session_id, '没有对应的录音会话')
                return
            self._clear_timer()
            self.phase = 'transcribing'
            capture, self.capture = self.capture, None
            try:
                pcm = await capture.stop()
                if len(pcm) < 3200:
                    raise ValueError('录音过短或没有音频，请检查麦克风')
            except Exception as exc:
                await capture.cancel()
                self.phase, self.id = 'idle', None
                await self.error(session_id, str(exc))
                return
            await self.emit({'type': 'transcribing', 'id': session_id})
            self.worker = asyncio.create_task(self._decode(session_id, pcm))

    async def _decode(self, session_id, pcm):
        try:
            text = await asyncio.to_thread(self.recognize, pcm)
            if not isinstance(text, str) or not text.strip():
                raise ValueError('没有识别到有效语音，请重试')
            text = text.strip()
            if len(text.encode('utf-8')) > 8192:
                raise ValueError('识别结果过长，请分成短句输入')
            # Dictation must not contain control keys/newlines, especially in terminals.
            text = ''.join(' ' if c.isspace() else c for c in text if ord(c) >= 32 or c.isspace())
            event = {'type': 'result', 'id': session_id, 'text': text}
        except Exception as exc:
            event = {'type': 'error', 'id': session_id, 'message': f'识别失败：{exc}'}
        async with self.lock:
            if not self.closed and self.id == session_id and self.phase == 'transcribing':
                self.id, self.phase = None, 'idle'
                try:
                    await self.emit(event)
                except (ConnectionError, asyncio.TimeoutError):
                    # The peer can disappear between the final focus check and write.
                    # Consume delivery failure here so close() still releases ownership.
                    self.closed = True

    async def cancel(self, session_id):
        async with self.lock:
            if self.closed:
                return
            if session_id != self.id or self.phase == 'idle':
                await self.error(session_id, '没有对应的语音会话')
                return
            self._clear_timer()
            if self.capture:
                await self.capture.cancel()
                self.capture = None
            self.id, self.phase = None, 'idle'
            await self.emit({'type': 'cancelled', 'id': session_id})

    async def close(self):
        async with self.lock:
            self.closed = True
            self._clear_timer()
            if self.capture:
                await self.capture.cancel()
                self.capture = None
            self.id, self.phase = None, 'idle'
        # Do not cancel a to_thread future: that would hide a still-running inference.
        if self.worker:
            await asyncio.shield(self.worker)
