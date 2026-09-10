"""Private, bounded JSONL protocol endpoint for a single Fcitx5 client."""

import asyncio
import fcntl
import json
import os
import socket
import stat
import struct
from pathlib import Path

from .session import Session
from .streaming_session import StreamingSession

MAX_LINE = 65536


class VoiceServer:
    def __init__(self, path, capture_factory, recognize, max_seconds=30, streaming=False):
        self.path = Path(path)
        self.capture_factory = capture_factory
        self.recognize = recognize
        self.max_seconds = max_seconds
        self.streaming = streaming
        self.server = None
        self.lock_fd = None
        self.owner = False
        self.tasks = set()
        self.writers = set()
        self.inode = None

    async def start(self):
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = self.path.parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
            raise RuntimeError('Socket 目录必须属于当前用户，且不能是符号链接')
        self.path.parent.chmod(0o700)
        self.lock_fd = os.open(self.path.with_suffix('.lock'),
                               os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            try:
                fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError('语音服务已在运行') from exc
            if self.path.exists() or self.path.is_symlink():
                if not stat.S_ISSOCK(self.path.lstat().st_mode):
                    raise RuntimeError('Socket 路径已被非 socket 文件占用')
                probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                try:
                    probe.settimeout(0.2)
                    probe.connect(str(self.path))
                except ConnectionRefusedError:
                    self.path.unlink()
                else:
                    raise RuntimeError('Socket 已有服务监听')
                finally:
                    probe.close()
            self.server = await asyncio.start_unix_server(self._client, str(self.path), limit=MAX_LINE)
            self.path.chmod(0o600)
            self.inode = self.path.stat().st_ino
        except BaseException:
            os.close(self.lock_fd)
            self.lock_fd = None
            raise

    async def _client(self, reader, writer):
        task = asyncio.current_task()
        self.tasks.add(task)
        self.writers.add(writer)
        session = None

        async def emit(event):
            if writer.is_closing():
                raise ConnectionError('语音客户端已断开')
            writer.write(json.dumps(event, ensure_ascii=False).encode('utf-8') + b'\n')
            try:
                await asyncio.wait_for(writer.drain(), 2)
            except (ConnectionError, asyncio.TimeoutError):
                writer.close()
                raise

        try:
            raw = writer.get_extra_info('socket').getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
            _, uid, _ = struct.unpack('3i', raw)
            if uid != os.getuid():
                return
            if self.owner:
                await emit({'type': 'busy', 'message': '语音服务已有连接，请稍后重试'})
                return
            self.owner = True
            session_class = StreamingSession if self.streaming else Session
            session = session_class(self.capture_factory, self.recognize, emit, self.max_seconds)
            await emit({'type': 'ready', 'protocol': 2 if self.streaming else 1})
            while True:
                try:
                    line = await reader.readline()
                except ValueError:
                    await emit({'type': 'error', 'message': '协议消息过长'})
                    break
                if not line:
                    break
                if len(line) > MAX_LINE or not line.endswith(b'\n'):
                    await emit({'type': 'error', 'message': '协议消息过长或不完整'})
                    break
                valid_id = None
                try:
                    command = json.loads(line)
                    if not isinstance(command, dict):
                        raise ValueError('消息必须是 JSON 对象')
                    kind, session_id = command.get('type'), command.get('id')
                    if not isinstance(session_id, str) or not session_id or len(session_id.encode('utf-8')) > 128:
                        raise ValueError('无效的会话标识')
                    if any(ord(c) < 32 for c in session_id):
                        raise ValueError('无效的会话标识')
                    valid_id = session_id
                    if kind not in {'start', 'stop', 'cancel'}:
                        raise ValueError('未知命令')
                except (ValueError, TypeError, UnicodeError, RecursionError):
                    error = {'type': 'error', 'message': '无效的协议消息'}
                    if valid_id is not None:
                        error['id'] = valid_id
                    await emit(error)
                    continue
                await getattr(session, kind)(session_id)
        except (ConnectionError, BrokenPipeError, asyncio.TimeoutError):
            pass
        finally:
            try:
                if session:
                    await session.close()
            finally:
                if session:
                    self.owner = False
                writer.close()
                try:
                    await writer.wait_closed()
                except (ConnectionError, BrokenPipeError):
                    pass
                self.writers.discard(writer)
                self.tasks.discard(task)

    async def close(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        for writer in list(self.writers):
            writer.close()
        if self.tasks:
            await asyncio.gather(*list(self.tasks), return_exceptions=True)
        if self.inode and self.path.exists() and self.path.stat().st_ino == self.inode:
            self.path.unlink()
        if self.lock_fd is not None:
            os.close(self.lock_fd)
            self.lock_fd = None
