import asyncio
import threading
import unittest

from fcitx5_voice.streaming_session import StreamingSession


class StreamCapture:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.active = False

    async def start(self):
        self.active = True

    async def chunks(self):
        while (chunk := await self.queue.get()) is not None:
            yield chunk

    async def stop(self):
        self.active = False
        self.queue.put_nowait(None)

    async def cancel(self):
        await self.stop()


class Decoder:
    def accept(self, pcm):
        return [('partial', '明天上午')] if pcm == b'first' else [('final', '明天下午。')]

    def finish(self):
        return [('final', '三点开会。')]


class Recognizer:
    def __init__(self, decoder=None):
        self.decoder = decoder or Decoder()

    def create_decoder(self):
        return self.decoder


class StreamingSessionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.events = []
        self.capture = StreamCapture()

        async def emit(event):
            self.events.append(event)

        self.session = StreamingSession(lambda: self.capture, Recognizer(), emit)

    async def asyncTearDown(self):
        await self.session.close()

    async def wait_for(self, kind):
        async with asyncio.timeout(2):
            while not any(e['type'] == kind for e in self.events):
                await asyncio.sleep(0.001)

    async def test_partial_and_sentence_commit_arrive_before_stop_and_tail_is_flushed(self):
        await self.session.start('a')
        await self.capture.queue.put(b'first')
        await self.wait_for('partial')
        self.assertTrue(self.capture.active)
        await self.capture.queue.put(b'second')
        await self.wait_for('final')
        self.assertTrue(self.capture.active)
        await self.session.stop('a')
        await self.session.stop('a')
        await self.wait_for('finished')
        self.assertEqual(self.events, [
            {'type': 'recording', 'id': 'a'},
            {'type': 'partial', 'id': 'a', 'segment': 1, 'seq': 1, 'text': '明天上午'},
            {'type': 'final', 'id': 'a', 'segment': 1, 'seq': 2, 'text': '明天下午。'},
            {'type': 'transcribing', 'id': 'a'},
            {'type': 'final', 'id': 'a', 'segment': 2, 'seq': 3, 'text': '三点开会。'},
            {'type': 'finished', 'id': 'a'},
        ])
        self.assertFalse(self.capture.active)

    async def test_cancel_during_inference_suppresses_late_results(self):
        entered, release = threading.Event(), threading.Event()

        class Delayed(Decoder):
            def accept(self, pcm):
                entered.set()
                release.wait(2)
                return [('partial', '过期'), ('final', '过期')]

        self.session.recognize = Recognizer(Delayed())
        await self.session.start('old')
        await self.capture.queue.put(b'first')
        try:
            async with asyncio.timeout(1):
                while not entered.is_set():
                    await asyncio.sleep(0.001)
            await self.session.cancel('old')
            self.assertFalse(self.capture.active)
        finally:
            release.set()
        await self.session.close()
        self.assertEqual([e['type'] for e in self.events], ['recording', 'cancelled'])

    async def test_wrong_id_preserves_live_capture_and_timeout_flushes(self):
        self.session.max_seconds = 0.03
        await self.session.start('a')
        await self.session.stop('wrong')
        await self.session.cancel('wrong')
        self.assertTrue(self.capture.active)
        await self.wait_for('finished')
        self.assertEqual([e['id'] for e in self.events if e['type'] == 'final'], ['a'])
        self.assertFalse(self.capture.active)

    async def test_stream_failure_releases_microphone_and_reports_error(self):
        class Broken(Decoder):
            def accept(self, pcm):
                raise RuntimeError('音频队列溢出')

        self.session.recognize = Recognizer(Broken())
        await self.session.start('a')
        await self.capture.queue.put(b'first')
        await self.wait_for('error')
        self.assertFalse(self.capture.active)
        self.assertFalse(any(e['type'] == 'finished' for e in self.events))

    async def test_disconnect_on_partial_releases_capture_without_late_final(self):
        async def disconnected(event):
            if event['type'] == 'partial':
                raise ConnectionResetError('closed')
            self.events.append(event)

        self.session.emit = disconnected
        await self.session.start('a')
        await self.capture.queue.put(b'first')
        async with asyncio.timeout(2):
            while self.capture.active:
                await asyncio.sleep(0.001)
        await self.session.close()
        self.assertEqual([e['type'] for e in self.events], ['recording'])

    async def test_empty_revision_control_characters_and_duplicate_partials(self):
        class Revising(Decoder):
            def accept(self, pcm):
                return [('partial', '命令\n下一行\x7f'), ('partial', '命令\n下一行\x7f'),
                        ('partial', ''), ('final', ''), ('partial', '新句')]

        self.session.recognize = Recognizer(Revising())
        await self.session.start('a')
        await self.capture.queue.put(b'first')
        async with asyncio.timeout(2):
            while len(self.events) < 5:
                await asyncio.sleep(0.001)
        self.assertEqual([(e['type'], e.get('text'), e.get('segment'), e.get('seq'))
                          for e in self.events[1:]], [
            ('partial', '命令 下一行', 1, 1), ('partial', '', 1, 2),
            ('final', '', 1, 3), ('partial', '新句', 2, 4)])

    async def test_english_segments_keep_word_boundaries_in_preedit_and_commit(self):
        class English(Decoder):
            def accept(self, pcm):
                return [('final', 'Hello world'), ('partial', 'how are'),
                        ('final', 'how are you?'), ('final', 'Fine'), ('final', '中文')]

        self.session.recognize = Recognizer(English())
        await self.session.start('a')
        await self.capture.queue.put(b'first')
        async with asyncio.timeout(2):
            while len(self.events) < 6:
                await asyncio.sleep(0.001)
        self.assertEqual([e['text'] for e in self.events[1:]],
                         ['Hello world', ' how are', ' how are you?', ' Fine', '中文'])

    async def test_finalize_only_changes_finals_including_stop_tail(self):
        seen = []

        def finalize(text):
            seen.append(text)
            return text.replace('。', '！')

        self.session.finalize = finalize
        await self.session.start('a')
        await self.capture.queue.put(b'first')
        await self.wait_for('partial')
        self.assertEqual(seen, [])
        self.assertEqual(self.events[-1]['text'], '明天上午')
        await self.capture.queue.put(b'second')
        await self.wait_for('final')
        self.assertEqual(self.events[-1]['text'], '明天下午！')
        await self.session.stop('a')
        await self.wait_for('finished')
        self.assertEqual(seen, ['明天下午。', '三点开会。'])
        self.assertEqual([e['text'] for e in self.events if e['type'] == 'final'],
                         ['明天下午！', '三点开会！'])

    async def test_cancel_during_final_processing_drops_result_without_blocking_loop(self):
        entered, release = threading.Event(), threading.Event()

        def delayed(text):
            entered.set()
            release.wait(2)
            return text + '！'

        self.session.finalize = delayed
        await self.session.start('a')
        await self.capture.queue.put(b'second')
        try:
            async with asyncio.timeout(1):
                while not entered.is_set():
                    await asyncio.sleep(0.001)
            await asyncio.wait_for(self.session.cancel('a'), 0.2)
            self.assertFalse(self.capture.active)
        finally:
            release.set()
        await self.session.close()
        self.assertEqual([e['type'] for e in self.events], ['recording', 'cancelled'])

    async def test_correction_result_is_dropped_when_cancelled_during_final_inference(self):
        from fcitx5_voice.refined_recognizer import RefinedStreamingRecognizer
        from test_refined_recognizer import Preview, BLOCK
        entered, release = threading.Event(), threading.Event()

        def correct(pcm):
            entered.set()
            release.wait(2)
            return '取消后不能输入这段文字。'

        self.session.recognize = RefinedStreamingRecognizer(Preview(), correct)
        await self.session.start('old')
        await self.capture.queue.put(BLOCK)
        await self.session.stop('old')
        try:
            async with asyncio.timeout(1):
                while not entered.is_set():
                    await asyncio.sleep(0.001)
            await asyncio.wait_for(self.session.cancel('old'), 0.2)
        finally:
            release.set()
        await self.session.worker
        self.assertEqual([e['type'] for e in self.events],
                         ['recording', 'transcribing', 'cancelled'])

    async def test_endpoint_correction_then_stop_commit_each_audio_segment_once(self):
        from fcitx5_voice.refined_recognizer import RefinedStreamingRecognizer
        from test_refined_recognizer import Preview, BLOCK
        seen = []

        def correct(pcm):
            seen.append(pcm)
            return '第一句。' if len(seen) == 1 else '第二句。'

        self.session.recognize = RefinedStreamingRecognizer(
            Preview([[('partial', '第一'), ('final', '错误草稿')], [('partial', '第二')]]), correct)
        await self.session.start('a')
        await self.capture.queue.put(BLOCK)
        await self.wait_for('final')
        self.assertTrue(self.capture.active)
        second = b'\x00\x20' * 1600
        await self.capture.queue.put(second)
        await self.session.stop('a')
        await self.wait_for('finished')
        self.assertEqual(seen, [BLOCK, second])
        self.assertEqual([(e['segment'], e['text']) for e in self.events if e['type'] == 'final'],
                         [(1, '第一句。'), (2, '第二句。')])
