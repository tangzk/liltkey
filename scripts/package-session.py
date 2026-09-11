#!/usr/bin/env python3
"""Debian lifecycle bridge: dispatch to user managers, never configure as root."""

import argparse
import pwd
import subprocess


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['configure', 'remove', 'upgrade'])
    args = parser.parse_args(argv)
    try:
        result = subprocess.run(['loginctl', 'list-users', '--no-legend'],
                                check=True, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        print('没有可用的桌面用户管理器；自动配置将在下次桌面登录时启动。')
        return 0
    for line in result.stdout.splitlines():
        try:
            uid = int(line.split()[0])
            if uid == 0:
                continue
            user = pwd.getpwuid(uid)
            prefix = ['runuser', '-u', user.pw_name, '--', 'env', '-i',
                      f'HOME={user.pw_dir}', f'USER={user.pw_name}', f'LOGNAME={user.pw_name}',
                      'PATH=/usr/bin:/bin', f'XDG_RUNTIME_DIR=/run/user/{uid}',
                      f'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{uid}/bus',
                      'systemctl', '--user']

            def control(*arguments, check=True):
                return subprocess.run([*prefix, *arguments], check=check,
                                      capture_output=True, text=True, timeout=30)

            if args.action in {'remove', 'upgrade'}:
                # Stop only setup during upgrades; the old recognizer can continue
                # until replacement files and models are ready.
                units = ['fcitx5-voice-setup.service']
                if args.action == 'remove':
                    units.append('fcitx5-voice.service')
                control('stop', *units, check=False)
                if args.action == 'remove':
                    control('disable', 'fcitx5-voice.service', check=False)
                continue
            if control('is-active', 'graphical-session.target', check=False).returncode:
                continue
            environment = control('show-environment').stdout.splitlines()
            if not any(line.startswith(('DISPLAY=', 'WAYLAND_DISPLAY=')) and line.split('=', 1)[1]
                       for line in environment):
                continue
            control('daemon-reload')
            control('start', '--no-block', 'fcitx5-voice-setup.service')
        except (OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError) as exc:
            print(f'用户自动配置已延后至下次桌面登录：{type(exc).__name__}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
