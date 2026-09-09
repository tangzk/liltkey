"""Capture raw PCM with GStreamer; never write microphone audio to disk."""

import asyncio
import shutil


class GStreamerCapture:
    def __init__(self, device='', max_seconds=30, source=None):
        self.source = source or ['pulsesrc'] + ([f'device={device}'] if device else [])
        self.max_bytes = int(max_seconds * 16000 * 2)
        self.pcm = bytearray()
        self.stderr = bytearray()
        self.process = None
        self.readers = []

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
        while chunk := await self.process.stdout.read(8192):
            remaining = self.max_bytes - len(self.pcm)
            if remaining > 0:
                self.pcm.extend(chunk[:remaining])

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
        await self._finish()
        result = bytes(self.pcm[:len(self.pcm) // 2 * 2])
        self.pcm.clear()
        if self.process and self.process.returncode not in {0, -15}:
            detail = self.stderr.decode('utf-8', errors='replace').strip()[:1000]
            raise RuntimeError(f'音频采集失败：{detail or "请检查麦克风设备"}')
        return result

    async def cancel(self):
        await self._finish()
        self.pcm.clear()
