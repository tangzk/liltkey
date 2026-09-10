"""Desktop service and explicit diagnostics; diagnostics never open the mic."""

import argparse
import asyncio
import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import wave
from dataclasses import replace
from functools import partial
from pathlib import Path

from .config import config_path, load_config, socket_path
from .text import finalize_text, format_segment


def build_finalizer(config):
    punctuate = None
    if config.punctuation:
        from .punctuation import PunctuationRestorer
        punctuate = PunctuationRestorer(config)
    return partial(finalize_text, punctuate=punctuate)


def apply_overrides(config, backend=None, model_dir=None, streaming_model_dir=None):
    updates = {}
    if backend:
        updates['backend'] = backend
    if model_dir:
        updates['model_dir'] = model_dir.expanduser().resolve()
    if streaming_model_dir:
        updates['streaming_model_dir'] = streaming_model_dir.expanduser().resolve()
    result = replace(config, **updates)
    if result.backend == 'streaming' and result.language != 'auto':
        raise ValueError('streaming 双语模型自动识别中英文，language 必须是 auto')
    return result


async def serve(config):
    from .audio import GStreamerCapture
    from .server import VoiceServer
    streaming = config.backend == 'streaming'
    if streaming:
        from .streaming_recognizer import StreamingRecognizer
        recognizer_type = StreamingRecognizer
    else:
        from .recognizer import SenseVoiceRecognizer
        recognizer_type = SenseVoiceRecognizer
    print(f'正在加载{"streaming" if streaming else "offline"}模型（不会启动麦克风）…',
          flush=True)
    recognize = await asyncio.to_thread(recognizer_type, config)
    finalize = await asyncio.to_thread(build_finalizer, config) if streaming else None
    server = VoiceServer(socket_path(),
                         lambda: GStreamerCapture(config.device, config.max_seconds,
                                                  streaming=streaming),
                         recognize, config.max_seconds, streaming=streaming, finalize=finalize)
    stopped = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stopped.set)
    await server.start()
    print(f'{config.backend} 识别服务就绪：{socket_path()}', flush=True)
    try:
        await stopped.wait()
    finally:
        await server.close()


def doctor(config):
    checks = []

    def check(name, ok, detail):
        checks.append(bool(ok))
        print(f'{"OK" if ok else "FAIL"}  {name}: {detail}')

    for name in ('gst-launch-1.0', 'gst-inspect-1.0', 'fcitx5'):
        check(name, shutil.which(name), shutil.which(name) or '未安装')
    if shutil.which('gst-inspect-1.0'):
        for element in ('pulsesrc', 'audioconvert', 'audioresample', 'fdsink'):
            result = subprocess.run(['gst-inspect-1.0', element], capture_output=True)
            check(element, result.returncode == 0, 'GStreamer 插件')
    for module in ('numpy', 'sherpa_onnx'):
        check(module, importlib.util.find_spec(module), 'Python 依赖')
    if config.backend == 'streaming':
        model_dir = config.streaming_model_dir
        filenames = ('encoder-epoch-99-avg-1.int8.onnx', 'decoder-epoch-99-avg-1.onnx',
                     'joiner-epoch-99-avg-1.int8.onnx', 'tokens.txt')
    else:
        model_dir = config.model_dir
        filenames = ('model.int8.onnx', 'tokens.txt')
    for filename in filenames:
        path = model_dir / filename
        check(filename, path.is_file(), path)
    if config.backend == 'streaming' and config.punctuation:
        path = config.punctuation_model_dir / 'model.int8.onnx'
        check('标点模型', path.is_file(), path)
    check('桌面运行目录', os.environ.get('XDG_RUNTIME_DIR'), os.environ.get('XDG_RUNTIME_DIR', '未设置'))
    print(f'配置文件：{config_path()}')
    print(f'后端：{config.backend}；CPU 线程：{config.threads}；语言：{config.language}；'
          f'录音上限：{config.max_seconds} 秒')
    if config.backend == 'streaming':
        print(f'自动标点：{"开启" if config.punctuation else "关闭"}')
    print('诊断未访问麦克风。')
    return 0 if all(checks) else 1


def transcribe(config, filename, repeats):
    with wave.open(str(filename), 'rb') as wav:
        if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getframerate() != 16000:
            raise ValueError('样本必须是 16 kHz、单声道、16-bit PCM WAV')
        if wav.getnframes() > 30 * 16000:
            raise ValueError('样本最多 30 秒；长音频请先分段')
        pcm = wav.readframes(wav.getnframes())
    start = time.perf_counter()
    if config.backend == 'streaming':
        from .streaming_recognizer import StreamingRecognizer
        recognize = StreamingRecognizer(config)
        finalize = build_finalizer(config)
    else:
        from .recognizer import SenseVoiceRecognizer
        recognize = SenseVoiceRecognizer(config)
    load_seconds = time.perf_counter() - start
    timings = []
    for _ in range(repeats):
        start = time.perf_counter()
        if config.backend == 'streaming':
            decoder = recognize.create_decoder()
            final, current, committed_tail = [], '', ''

            def apply(events):
                nonlocal current, committed_tail
                for kind, value in events:
                    if kind == 'final':
                        value = finalize(value)
                    value = format_segment(value, committed_tail, mixed_spacing=True)
                    if kind == 'final':
                        final.append(value)
                        current = ''
                        if value:
                            committed_tail = value[-1]
                    else:
                        current = value

            for offset in range(0, len(pcm), 3200):
                apply(decoder.accept(pcm[offset:offset + 3200]))
            apply(decoder.finish())
            text = ''.join(final) + current
        else:
            text = recognize(pcm)
        timings.append(time.perf_counter() - start)
    print(json.dumps({'text': text, 'audio_seconds': len(pcm) / 32000,
                      'model_load_seconds': round(load_seconds, 3),
                      'decode_seconds': [round(t, 3) for t in timings],
                      'threads': config.threads, 'backend': config.backend},
                     ensure_ascii=False, indent=2))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description='Fcitx5 本地语音输入服务')
    parser.add_argument('--config', type=Path, help='TOML 配置文件')
    parser.add_argument('--backend', choices=('streaming', 'offline'), help='覆盖识别后端')
    parser.add_argument('--model-dir', type=Path, help='覆盖配置中的模型目录')
    parser.add_argument('--streaming-model-dir', type=Path, help='覆盖流式模型目录')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('serve', help='启动服务；等待插件触发录音')
    commands.add_parser('doctor', help='检查依赖和模型，不录音')
    commands.add_parser('devices', help='列出音频设备，不录音')
    trans = commands.add_parser('transcribe', help='转写显式指定的短 WAV 文件')
    trans.add_argument('wav', type=Path)
    trans.add_argument('--repeat', type=int, choices=range(1, 11), default=1)
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config, backend=args.backend)
        config = apply_overrides(config, args.backend, args.model_dir, args.streaming_model_dir)
        if args.command == 'serve':
            asyncio.run(serve(config))
            return 0
        if args.command == 'doctor':
            return doctor(config)
        if args.command == 'devices':
            if shutil.which('pactl'):
                return subprocess.run(['pactl', 'list', 'short', 'sources']).returncode
            if shutil.which('wpctl'):
                return subprocess.run(['wpctl', 'status', '-n']).returncode
            raise RuntimeError('请安装 pulseaudio-utils，使用 pactl list short sources 查询设备')
        return transcribe(config, args.wav, args.repeat)
    except (OSError, ValueError, RuntimeError, ImportError) as exc:
        print(f'错误：{exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
