"""Capture raw PCM with GStreamer; never write microphone audio to disk."""

import asyncio
import shutil


class GStreamerCapture:
    def __init__(self, device='', max_seconds=30, source=None, streaming=False):
        self.source = source or ['pulsesrc'] + ([f'device={device}'] if device else [])
        self.max_bytes = int(max_seconds * 16000 * 2)
        self.pcm = bytearray()
        self.stderr = bytearray()
        self.process = None
        self.readers = []
        self.streaming = streaming
        # At most two seconds of 100 ms PCM blocks; never accumulate a recording.
        self.queue = asyncio.Queue(maxsize=20)
        self.available = asyncio.Event()
        self.eof = False
        self.stopping = False
        self.cancelled = False
        self.failure = None

    async def start(self):
        executable = shutil.which('gst-launch-1.0')
        if not executable:
            raise RuntimeError('缺少 gst-launch-1.0，请安装 gstreamer1.0-tools 和 plugins-good')
        args = [executable, '-q', *self.source, '!', 'audioconvert', '!', 'audioresample',
                '!', 'audio/x-raw,format=S16LE,rate=16000,channels=1', '!', 'fdsink', 'fd=1']
        self.process = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        self.readers = [asyncio.create_task(self._read_pcm()), asyncio.create_task(self._read_errors())]

    async def _read_pcm(self):
        if self.streaming:
            await self._read_stream()
            return
        while chunk := await self.process.stdout.read(8192):
            remaining = self.max_bytes - len(self.pcm)
            if remaining > 0:
                self.pcm.extend(chunk[:remaining])

    async def _read_stream(self):
        total = 0
        pending = b''
        try:
            while chunk := await self.process.stdout.read(3200):
                pending += chunk
                size = min(len(pending) // 2 * 2, max(0, self.max_bytes - total))
                if size:
                    try:
                        self.queue.put_nowait(pending[:size])
                    except asyncio.QueueFull:
                        raise RuntimeError('音频队列已满，识别速度跟不上录音，请减少 CPU 负载')
                    total += size
                    self.available.set()
                pending = pending[len(pending) // 2 * 2:]
            if not self.stopping:
                raise RuntimeError('麦克风采集中断，请检查设备后重试')
            if pending:
                raise RuntimeError('采集到不完整的 PCM 音频')
        except Exception as exc:
            self.failure = exc
            if self.process.returncode is None:
                try:
                    self.process.terminate()
                except ProcessLookupError:
                    pass
            # Keep draining the pipe so process.wait() can finish even after overflow.
            while await self.process.stdout.read(8192):
                pass
        finally:
            self.eof = True
            self.available.set()

    async def chunks(self):
        if not self.streaming:
            raise RuntimeError('未启用流式采集')
        while True:
            self.available.clear()
            if self.cancelled:
                return
            if self.failure:
                raise self.failure
            if not self.queue.empty():
                yield self.queue.get_nowait()
            elif self.eof:
                return
            else:
                await self.available.wait()

    async def _read_errors(self):
        while chunk := await self.process.stderr.read(4096):
            self.stderr.extend(chunk[:max(0, 8192 - len(self.stderr))])

    async def _finish(self):
        if not self.process:
            return
        if self.process.returncode is None:
            try:
                self.process.terminate()
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(self.process.wait(), 1)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()
        await asyncio.gather(*self.readers)

    async def stop(self):
        self.stopping = True
        await self._finish()
        if self.failure:
            raise self.failure
        result = bytes(self.pcm[:len(self.pcm) // 2 * 2])
        self.pcm.clear()
        if self.process and self.process.returncode not in {0, -15}:
            detail = self.stderr.decode('utf-8', errors='replace').strip()[:1000]
            raise RuntimeError(f'音频采集失败：{detail or "请检查麦克风设备"}')
        return result

    async def cancel(self):
        self.cancelled = True
        self.stopping = True
        self.available.set()
        await self._finish()
        self.pcm.clear()
        while not self.queue.empty():
            self.queue.get_nowait()
