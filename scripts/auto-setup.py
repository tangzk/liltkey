#!/usr/bin/env python3
"""Initialize an installed deb in the desktop user's own session."""

import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
UNIT = 'fcitx5-voice-setup.service'
DESKTOP_ENV = ('DISPLAY', 'WAYLAND_DISPLAY', 'XAUTHORITY', 'XDG_CURRENT_DESKTOP',
               'XDG_SESSION_TYPE', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME')


def notify(message):
    try:
        subprocess.run(['notify-send', '--app-name=Fcitx5 语音输入',
                        'Fcitx5 语音输入', message], timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        pass  # Notifications must never decide installation success.


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--launch', action='store_true', help='由桌面登录自动启动后台配置')
    args = parser.parse_args(argv)
    version_file = ROOT / 'PACKAGE_VERSION'
    if not version_file.exists():
        return 0  # Package removed while a login job was queued.
    if os.getuid() == 0 or not os.environ.get('XDG_RUNTIME_DIR') or not (
            os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
        print('自动配置需要普通用户的图形桌面会话。', file=sys.stderr)
        return 78  # systemd waits for the next desktop login instead of retrying.
    try:
        if args.launch:
            names = [name for name in DESKTOP_ENV if os.environ.get(name)]
            subprocess.run(['systemctl', '--user', 'import-environment', *names], check=True)
            subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
            subprocess.run(['systemctl', '--user', 'start', '--no-block', UNIT], check=True)
            return 0
        state = Path(os.environ.get('XDG_DATA_HOME', Path.home()/'.local/share'))/'fcitx5-voice'
        state.mkdir(parents=True, exist_ok=True)
        with (state/'auto-setup.lock').open('w') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return 0
            # ctime also changes on a same-version reinstall; package removal and
            # reinstall must not be mistaken for an already configured installation.
            generation = f'{version_file.read_text().strip()}:{version_file.stat().st_ctime_ns}'
            status_file = state/'setup-status.json'
            try:
                previous = json.loads(status_file.read_text())
            except (OSError, ValueError):
                previous = {}
            if not isinstance(previous, dict):
                previous = {}
            if previous.get('generation') == generation and previous.get('status') == 'ready':
                return 0

            def status(value):
                temporary = status_file.with_suffix('.tmp')
                temporary.write_text(json.dumps({'generation': generation, 'status': value}))
                temporary.replace(status_file)

            retry = previous.get('generation') == generation and previous.get('status') == 'failed'
            status('installing')
            if not retry:
                notify('正在自动配置并下载语音模型，首次需要联网。完成后会通知您。')
            try:
                subprocess.run([sys.executable, str(ROOT/'scripts/setup.py'),
                                '--service-only', '--desktop-service'], check=True)
            except (OSError, subprocess.CalledProcessError):
                status('failed')
                if not retry:
                    notify('自动配置暂未完成，5 分钟后自动重试。详情见 fcitx5-voice-setup 服务日志。')
                return 1
            status('ready')
            notify('语音输入已就绪：Ctrl+Alt+V 开始／结束。首次切换输入法请注销并重新登录。')
            return 0
    except (OSError, subprocess.SubprocessError) as exc:
        print(f'自动配置失败：{exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
