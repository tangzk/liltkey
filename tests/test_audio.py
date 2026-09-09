import asyncio
import shutil
import unittest

from fcitx5_voice.audio import GStreamerCapture


@unittest.skipUnless(shutil.which('gst-launch-1.0'), 'GStreamer unavailable')
class AudioTests(unittest.IsolatedAsyncioTestCase):
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
