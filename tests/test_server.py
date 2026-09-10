import asyncio
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

from fcitx5_voice.server import VoiceServer
from test_session import Capture


class ServerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / 'voice/service.sock'
        self.capture = Capture()
        self.server = VoiceServer(self.path, lambda: self.capture, lambda pcm: '测试通过。')
        await self.server.start()
        self.connections = []

    async def asyncTearDown(self):
        for writer in self.connections:
            writer.close()
            await writer.wait_closed()
        await self.server.close()
        self.directory.cleanup()

    async def connect(self):
        reader, writer = await asyncio.open_unix_connection(str(self.path))
        self.connections.append(writer)
        greeting = await self.read(reader)
        return reader, writer, greeting

    async def read(self, reader):
        return json.loads(await asyncio.wait_for(reader.readline(), 2))

    async def send(self, writer, payload):
        writer.write(json.dumps(payload).encode() + b'\n')
        await writer.drain()

    async def test_real_socket_recording_result_and_private_permissions(self):
        reader, writer, greeting = await self.connect()
        self.assertEqual(greeting, {'type': 'ready', 'protocol': 1})
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.path.parent.stat().st_mode), 0o700)
        await self.send(writer, {'type': 'start', 'id': 's1'})
        self.assertEqual(await self.read(reader), {'type': 'recording', 'id': 's1'})
        await self.send(writer, {'type': 'stop', 'id': 's1'})
        self.assertEqual((await self.read(reader))['type'], 'transcribing')
        self.assertEqual(await self.read(reader), {'type': 'result', 'id': 's1', 'text': '测试通过。'})

    async def test_second_client_is_busy_and_cannot_own_microphone(self):
        await self.connect()
        reader, writer, greeting = await self.connect()
        self.assertEqual(greeting['type'], 'busy')
        self.assertEqual(await reader.read(), b'')

    async def test_streaming_socket_delivers_partial_before_stop_and_final_before_finished(self):
        from test_streaming_session import StreamCapture, Recognizer
        await self.server.close()
        self.capture = StreamCapture()
        self.server = VoiceServer(self.path, lambda: self.capture, Recognizer(), streaming=True)
        await self.server.start()
        reader, writer, greeting = await self.connect()
        self.assertEqual(greeting, {'type': 'ready', 'protocol': 2})
        await self.send(writer, {'type': 'start', 'id': 'live'})
        self.assertEqual((await self.read(reader))['type'], 'recording')
        await self.capture.queue.put(b'first')
        self.assertEqual(await self.read(reader), {
            'type': 'partial', 'id': 'live', 'segment': 1, 'seq': 1, 'text': '明天上午'})
        self.assertTrue(self.capture.active)
        await self.send(writer, {'type': 'stop', 'id': 'live'})
        self.assertEqual((await self.read(reader))['type'], 'transcribing')
        self.assertEqual(await self.read(reader), {
            'type': 'final', 'id': 'live', 'segment': 1, 'seq': 2, 'text': '三点开会。'})
        self.assertEqual(await self.read(reader), {'type': 'finished', 'id': 'live'})
        self.assertFalse(self.capture.active)

    async def test_socket_final_processing_keeps_partial_raw_and_restores_stop_punctuation(self):
        from test_streaming_session import StreamCapture, Recognizer
        from fcitx5_voice.text import finalize_text
        await self.server.close()
        self.capture = StreamCapture()
        self.server = VoiceServer(self.path, lambda: self.capture, Recognizer(), streaming=True,
                                 finalize=lambda text: finalize_text(text, lambda value: value.replace('。', '？')))
        await self.server.start()
        reader, writer, _ = await self.connect()
        await self.send(writer, {'type': 'start', 'id': 'punct'})
        await self.read(reader)
        await self.capture.queue.put(b'first')
        self.assertEqual((await self.read(reader))['text'], '明天上午')
        await self.send(writer, {'type': 'stop', 'id': 'punct'})
        self.assertEqual((await self.read(reader))['type'], 'transcribing')
        self.assertEqual((await self.read(reader))['text'], '三点开会？')
        self.assertEqual((await self.read(reader))['type'], 'finished')

    async def test_invalid_frames_do_not_start_microphone(self):
        reader, writer, _ = await self.connect()
        for line in [b'not-json\n', b'[]\n', b'{"type":"unknown","id":"a"}\n',
                     b'{"type":"start","id":"\\ud800"}\n']:
            writer.write(line)
            await writer.drain()
            self.assertEqual((await self.read(reader))['type'], 'error')
        self.assertFalse(self.capture.active)

    async def test_oversize_line_disconnects_and_closes_microphone(self):
        reader, writer, _ = await self.connect()
        await self.send(writer, {'type': 'start', 'id': 'a'})
        await self.read(reader)
        writer.write(b'x' * 65537 + b'\n')
        await writer.drain()
        self.assertEqual((await self.read(reader))['type'], 'error')
        self.assertEqual(await reader.read(), b'')
        self.assertFalse(self.capture.active)

    async def test_disconnect_releases_microphone(self):
        reader, writer, _ = await self.connect()
        await self.send(writer, {'type': 'start', 'id': 'a'})
        await self.read(reader)
        writer.close()
        await writer.wait_closed()
        async with asyncio.timeout(2):
            while self.capture.active:
                await asyncio.sleep(0.001)

    async def test_second_server_cannot_unlink_live_socket(self):
        other = VoiceServer(self.path, Capture, lambda pcm: '')
        with self.assertRaises(RuntimeError):
            await other.start()
        self.assertTrue(self.path.exists())
        _, _, greeting = await self.connect()
        self.assertEqual(greeting['type'], 'ready')

    async def test_does_not_remove_regular_file_at_socket_path(self):
        path = self.path.parent / 'other.sock'
        path.write_text('keep')
        other = VoiceServer(path, Capture, lambda pcm: '')
        with self.assertRaises(RuntimeError):
            await other.start()
        self.assertEqual(path.read_text(), 'keep')

    async def test_deep_json_does_not_cancel_valid_recording(self):
        reader, writer, _ = await self.connect()
        await self.send(writer, {'type': 'start', 'id': 'a'})
        await self.read(reader)
        writer.write(b'{"unused":' + b'[' * 2000 + b'0' + b']' * 2000 + b'}\n')
        await writer.drain()
        self.assertEqual((await self.read(reader))['type'], 'error')
        self.assertTrue(self.capture.active)
        await self.send(writer, {'type': 'cancel', 'id': 'a'})
        self.assertEqual((await self.read(reader))['type'], 'cancelled')

    async def test_unknown_command_preserves_valid_id(self):
        reader, writer, _ = await self.connect()
        await self.send(writer, {'type': 'unknown', 'id': 'a'})
        response = await self.read(reader)
        self.assertEqual(response['type'], 'error')
        self.assertEqual(response['id'], 'a')
