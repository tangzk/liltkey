#!/usr/bin/env python3
"""一条命令完成依赖、插件、模型、默认配置和桌面服务安装。"""

import argparse
import json
import os
from pathlib import Path
import shlex
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PACKAGES = [
    'fcitx5', 'fcitx5-frontend-gtk3', 'fcitx5-frontend-gtk4',
    'fcitx5-frontend-qt5', 'fcitx5-frontend-qt6', 'im-config',
    'python3-venv', 'gstreamer1.0-tools', 'gstreamer1.0-plugins-base',
    'gstreamer1.0-plugins-good', 'pulseaudio-utils',
]
BUILD_PACKAGES = [
    'build-essential', 'cmake', 'pkg-config', 'libfcitx5core-dev',
    'libfcitx5config-dev', 'libfcitx5utils-dev', 'libjson-c-dev',
]


def run(command, quiet=False):
    command = [str(part) for part in command]
    print('+ ' + shlex.join(command), flush=True)
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL if quiet else None)


def wait_ready(timeout=120):
    """Wait for loaded models and the protocol handshake, without opening the mic."""
    path = Path(os.environ['XDG_RUNTIME_DIR']) / 'fcitx5-voice/service.sock'
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.socket(socket.AF_UNIX) as client:
                client.settimeout(min(1, max(0.01, deadline - time.monotonic())))
                client.connect(str(path))
                data = b''
                while b'\n' not in data and len(data) <= 4096:
                    chunk = client.recv(4096)
                    if not chunk:
                        break
                    data += chunk
                event = json.loads(data.split(b'\n', 1)[0])
                # An existing Fcitx client can already own the ready server.
                if isinstance(event, dict) and event.get('type') in {'ready', 'busy'}:
                    return
        except (OSError, ValueError):
            pass
        time.sleep(min(0.25, max(0, deadline - time.monotonic())))
    raise RuntimeError('模型加载或服务启动超时。请查看 journalctl --user -u fcitx5-voice -n 30')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--deb', type=Path, help='安装指定 deb 并完成当前用户配置，无须编译')
    mode.add_argument('--service-only', action='store_true', help='完成已安装 deb 的用户配置')
    parser.add_argument('--desktop-service', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    step = '安装前检查'
    try:
        if sys.version_info < (3, 11):
            raise RuntimeError('需要 Python 3.11 或更新版本；当前目标系统为 Ubuntu 26.04。')
        if os.getuid() == 0:
            raise RuntimeError('请以桌面用户运行，不要在整个命令前加 sudo；系统依赖会自动请求 sudo。')
        if not os.environ.get('XDG_RUNTIME_DIR') or not (
                os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
            raise RuntimeError('请在已登录的 Linux 桌面终端运行安装命令。')
        if args.deb and not args.deb.is_file():
            raise RuntimeError(f'找不到安装包：{args.deb}')
        sys.path.insert(0, str(ROOT / 'src'))
        from fcitx5_voice.config import load_config
        config = load_config()  # Validate existing preferences before changing the host.
        run(['systemctl', '--user', 'show-environment'], quiet=True)

        if not args.service_only:
            step = '系统依赖安装'
            run(['sudo', 'apt-get', 'update'])
            packages = RUNTIME_PACKAGES + ([] if args.deb else BUILD_PACKAGES)
            run(['sudo', 'apt-get', 'install', '-y', *packages,
                 *([str(args.deb.resolve())] if args.deb else [])])
            if args.deb:
                # postinst already queued this job; join it rather than racing a
                # second installer against the automatic package setup.
                run(['/usr/bin/fcitx5-voice-autosetup'])
                run(['systemctl', '--user', 'start', 'fcitx5-voice-setup.service'])
                return 0

        package_root = Path('/usr/share/fcitx5-voice') if args.deb else ROOT
        install = [sys.executable, package_root / 'scripts/install-user.py', '--quiet']
        if args.deb or args.service_only:
            install.append('--service-only')
            if (package_root/'PACKAGE_VERSION').exists():
                install.append('--package-managed')
        else:
            step = '插件编译'
            # Keep this build separate from developers' cached sysroot/test settings.
            build = ROOT / 'build/installer'
            run(['cmake', '-S', ROOT, '-B', build, '-DCMAKE_BUILD_TYPE=Release',
                 '-DBUILD_TESTING=OFF', '-DVOICEINPUT_SYSROOT='])
            run(['cmake', '--build', build, '--parallel', str(min(os.cpu_count() or 2, 4))])
            install.extend(['--plugin', build / 'voiceinput.so'])

        step = '用户运行环境与默认配置安装'
        run(install)
        step = '模型下载与校验'
        download = [sys.executable, package_root / 'scripts/download-model.py']
        if config.backend == 'offline':
            run([*download, '--backend', 'offline', '--dest', config.model_dir])
        else:
            run([*download, '--backend', 'streaming', '--no-punctuation',
                 '--dest', config.streaming_model_dir])
            if config.punctuation:
                run([*download, '--punctuation-only', '--dest', config.punctuation_model_dir])

        step = '依赖与模型检查'
        run([Path.home() / '.local/bin/fcitx5-voice', 'doctor'])
        step = '识别服务启动'
        run(['systemctl', '--user', 'daemon-reload'])
        run(['systemctl', '--user', 'enable', 'fcitx5-voice.service'])
        run(['systemctl', '--user', 'restart', 'fcitx5-voice.service'])
        print('等待识别模型加载完成（不录音）…', flush=True)
        wait_ready()
        step = '桌面输入法配置'
        run(['im-config', '-n', 'fcitx5'])
        if args.desktop_service:
            # The daemon must outlive the oneshot setup unit's cgroup.
            run(['systemd-run', '--user', '--collect',
                 f'--unit=fcitx5-voice-desktop-{os.getpid()}', '--property=Type=forking',
                 '--', '/usr/bin/fcitx5', '-rd'])
        else:
            run(['fcitx5', '-rd'])
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f'安装未完成（{step}）：{exc}\n修复后重新运行同一命令；已有配置和已校验模型会保留。',
              file=sys.stderr, flush=True)
        return 1
    print('安装完成，识别服务已就绪。默认 Ctrl+Alt+V 开始／结束，Esc 取消。\n'
          '首次安装或切换输入法后，请注销并重新登录，让所有应用使用 Fcitx5。\n'
          '已有个人语音配置和拼音配置保持不变。', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
