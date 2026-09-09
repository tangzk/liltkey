import asyncio
import threading
import unittest

from fcitx5_voice.session import Session


class Capture:
    def __init__(self):
        self.active = False
        self.pcm = b'\x00\x01' * 16000

    async def start(self):
        self.active = True

    async def stop(self):
        self.active = False
        return self.pcm

    async def cancel(self):
        self.active = False


class SessionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.events = []
        self.capture = Capture()
        self.recognized = []

        async def emit(event):
            self.events.append(event)

        def recognize(pcm):
            self.recognized.append(pcm)
            return '你好 Ubuntu。'

        self.session = Session(lambda: self.capture, recognize, emit, max_seconds=30)

    async def asyncTearDown(self):
        await self.session.close()

    async def wait_for(self, event_type):
        async with asyncio.timeout(2):
            while not any(e['type'] == event_type for e in self.events):
                await asyncio.sleep(0.001)

    async def test_stop_emits_one_result_and_closes_microphone(self):
        await self.session.start('a')
        self.assertTrue(self.capture.active)
        await self.session.stop('a')
        await self.wait_for('result')
        self.assertFalse(self.capture.active)
        self.assertEqual(self.events, [
            {'type': 'recording', 'id': 'a'},
            {'type': 'transcribing', 'id': 'a'},
            {'type': 'result', 'id': 'a', 'text': '你好 Ubuntu。'},
        ])
        self.assertEqual(self.recognized, [self.capture.pcm])

    async def test_wrong_id_cannot_stop_or_cancel_recording(self):
        await self.session.start('a')
        await self.session.stop('wrong')
        await self.session.cancel('wrong')
        self.assertTrue(self.capture.active)
        await self.session.cancel('a')
        self.assertFalse(self.capture.active)
        self.assertFalse(self.recognized)

    async def test_duplicate_start_preserves_original_session(self):
        await self.session.start('a')
        await self.session.start('b')
        await self.session.stop('a')
        await self.wait_for('result')
        self.assertEqual([e['id'] for e in self.events if e['type'] == 'result'], ['a'])

    async def test_stop_is_idempotent_during_inference_for_timer_hotkey_race(self):
        await self.session.start('a')
        await self.session.stop('a')
        await self.session.stop('a')
        await self.wait_for('result')
        self.assertFalse(any(e['type'] == 'error' for e in self.events))
        self.assertEqual(sum(e['type'] == 'result' for e in self.events), 1)

    async def test_empty_capture_is_error_without_model_call(self):
        self.capture.pcm = b''
        await self.session.start('a')
        await self.session.stop('a')
        await self.wait_for('error')
        self.assertFalse(self.recognized)
        self.assertFalse(self.capture.active)

    async def test_disconnect_cancels_capture_without_emitting(self):
        await self.session.start('a')
        await self.session.close()
        self.assertFalse(self.capture.active)
        self.assertEqual(len(self.events), 1)

    async def test_cancel_during_inference_discards_late_result(self):
        entered, release = threading.Event(), threading.Event()

        def delayed(pcm):
            entered.set()
            release.wait(2)
            return '过期结果'

        self.session.recognize = delayed
        await self.session.start('old')
        await self.session.stop('old')
        try:
            async with asyncio.timeout(1):
                while not entered.is_set():
                    await asyncio.sleep(0.001)
            await self.session.cancel('old')
            self.assertEqual(self.events[-1], {'type': 'cancelled', 'id': 'old'})
        finally:
            release.set()
        await asyncio.sleep(0.05)
        self.assertFalse(any(e['type'] == 'result' for e in self.events))
        await self.session.start('new')
        self.assertEqual(self.events[-1], {'type': 'recording', 'id': 'new'})

    async def test_limit_stops_recording_automatically(self):
        self.session.max_seconds = 0.02
        await self.session.start('a')
        await self.wait_for('result')
        self.assertFalse(self.capture.active)

    async def test_invalid_id_never_opens_microphone(self):
        for invalid in ['', 2, None, 'a' * 129, '\n']:
            await self.session.start(invalid)
        self.assertFalse(self.capture.active)
        self.assertTrue(all(e['type'] == 'error' for e in self.events))

    async def test_result_delivery_failure_does_not_break_disconnect_cleanup(self):
        original = self.session.emit

        async def dropped(event):
            if event['type'] == 'result':
                raise ConnectionResetError('peer disconnected')
            await original(event)

        self.session.emit = dropped
        await self.session.start('a')
        await self.session.stop('a')
        await asyncio.sleep(0.05)
        await self.session.close()
        self.assertFalse(self.capture.active)
        self.assertTrue(self.session.closed)


if __name__ == '__main__':
    unittest.main()
