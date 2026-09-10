import asyncio
import shutil
import unittest

from fcitx5_voice.audio import GStreamerCapture


@unittest.skipUnless(shutil.which('gst-launch-1.0'), 'GStreamer unavailable')
class AudioTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_yields_live_audio_and_stop_drains_without_retaining_recording(self):
        capture = GStreamerCapture(streaming=True, source=['audiotestsrc', 'is-live=true'])
        received = bytearray()

        async def consume():
            async for chunk in capture.chunks():
                self.assertEqual(len(chunk) % 2, 0)
                self.assertLessEqual(len(chunk), 3200)
                received.extend(chunk)

        await capture.start()
        task = asyncio.create_task(consume())
        try:
            async with asyncio.timeout(2):
                while len(received) < 3200:
                    await asyncio.sleep(0.001)
            self.assertIsNone(capture.process.returncode)
            await capture.stop()
            await asyncio.wait_for(task, 2)
            self.assertEqual(capture.pcm, b'')
            self.assertIsNotNone(capture.process.returncode)
        finally:
            await capture.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def test_stream_overflow_fails_explicitly_instead_of_dropping_audio(self):
        capture = GStreamerCapture(streaming=True, source=['audiotestsrc', 'num-buffers=1000'])
        await capture.start()
        try:
            await asyncio.wait_for(capture.readers[0], 2)
            with self.assertRaisesRegex(RuntimeError, '队列'):
                async for _ in capture.chunks():
                    pass
        finally:
            await capture.cancel()

    async def test_unexpected_stream_eof_is_error_and_cancel_wakes_consumer(self):
        capture = GStreamerCapture(streaming=True, source=['audiotestsrc', 'num-buffers=1'])
        await capture.start()
        try:
            with self.assertRaisesRegex(RuntimeError, '中断'):
                async for _ in capture.chunks():
                    pass
        finally:
            await capture.cancel()

    async def test_synthetic_source_is_bounded_pcm_and_process_is_reaped(self):
        capture = GStreamerCapture(max_seconds=1, source=['audiotestsrc', 'is-live=true', 'wave=sine'])
        await capture.start()
        await asyncio.sleep(0.3)
        pcm = await capture.stop()
        self.assertGreater(len(pcm), 3200)
        self.assertLessEqual(len(pcm), 32000)
        self.assertEqual(len(pcm) % 2, 0)
        self.assertIsNotNone(capture.process.returncode)

    async def test_cancel_reaps_process_and_discards_audio(self):
        capture = GStreamerCapture(source=['audiotestsrc', 'is-live=true'])
        await capture.start()
        await asyncio.sleep(0.05)
        await capture.cancel()
        self.assertIsNotNone(capture.process.returncode)
        self.assertEqual(capture.pcm, b'')

    async def test_missing_device_produces_actionable_error(self):
        capture = GStreamerCapture(source=['does-not-exist'])
        try:
            await capture.start()
            await asyncio.sleep(0.05)
            with self.assertRaises(RuntimeError):
                await capture.stop()
        except RuntimeError:
            pass
        finally:
            await capture.cancel()
