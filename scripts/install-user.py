#!/usr/bin/env python3
"""Install/uninstall user-owned files. Never restart the running input method."""

import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def locations():
    home = Path.home()
    data = Path(os.environ.get('XDG_DATA_HOME', home / '.local/share'))
    config = Path(os.environ.get('XDG_CONFIG_HOME', home / '.config'))
    return home, data, config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plugin', type=Path, default=ROOT / 'build/voiceinput.so')
    parser.add_argument('--runtime-python', type=Path, help='复用已有 Python 环境；该环境卸载时保留')
    parser.add_argument('--service-only', action='store_true', help='原生插件已由 deb 安装')
    parser.add_argument('--quiet', action='store_true', help='供一键安装调用，省略手动配置提示')
    parser.add_argument('--package-managed', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--uninstall', action='store_true')
    args = parser.parse_args()
    home, data, config = locations()
    state = data / 'fcitx5-voice'
    manifest = state / 'install-manifest.json'
    previous = json.loads(manifest.read_text()) if manifest.exists() else {'files': [], 'directories': []}
    if args.uninstall:
        if not manifest.exists():
            print('没有找到用户级安装记录。')
            return
        record = previous
        for filename in record['files']:
            Path(filename).unlink(missing_ok=True)
        for directory in record['directories']:
            if Path(directory).exists():
                shutil.rmtree(directory)
        manifest.unlink()
        print('已移除用户安装文件；个人配置和模型已保留。请重启 Fcitx5。')
        return
    if not args.service_only and not args.plugin.is_file():
        parser.error(f'请先编译插件，或用 --plugin 指定文件：{args.plugin}')

    managed = []
    if args.runtime_python:
        # abspath preserves venv symlinks; resolve() would bypass its environment.
        python = Path(os.path.abspath(args.runtime_python))
        subprocess.run([str(python), '-c', 'import numpy, sherpa_onnx'], check=True)
    else:
        runtime = state / 'venv'
        python = runtime / 'bin/python'
        uv = shutil.which('uv')
        if not python.exists():
            if uv:
                subprocess.run([uv, 'venv', '--python', '3.11', str(runtime)], check=True)
            else:
                subprocess.run([sys.executable, '-m', 'venv', str(runtime)], check=True)
        # Only dependencies need pip. Source is copied below, which also works when
        # this installer lives in the read-only /usr/share tree of a Debian package.
        with (ROOT / 'pyproject.toml').open('rb') as handle:
            dependencies = tomllib.load(handle)['project']['dependencies']
        if uv:
            subprocess.run([uv, 'pip', 'install', '--python', str(python), *dependencies], check=True)
        else:
            subprocess.run([str(python), '-m', 'pip', 'install', *dependencies], check=True)
        managed.append(str(runtime))

    files = []

    def write(path, text, mode=0o644):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        path.chmod(mode)
        files.append(str(path))

    library_dir = home / '.local/lib/fcitx5-voice'
    source = library_dir / 'service'
    source.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / 'src/fcitx5_voice', source / 'fcitx5_voice', dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    managed.append(str(source))
    if not args.service_only:
        plugin = library_dir / 'voiceinput.so'
        # The old inode may still be mapped by the running input method. Never
        # truncate it during an upgrade; replace the directory entry atomically.
        with tempfile.NamedTemporaryFile(dir=library_dir, prefix='.voiceinput-',
                                         suffix='.so', delete=False) as handle:
            temporary = Path(handle.name)
        try:
            shutil.copy2(args.plugin, temporary)
            temporary.replace(plugin)
        finally:
            temporary.unlink(missing_ok=True)
        files.append(str(plugin))
        addon = (ROOT / 'plugin/voiceinput.conf.in').read_text()
        addon = addon.replace('@PROJECT_VERSION@', '0.3.0')
        addon = '\n'.join('Library=' + str(plugin.with_suffix('')) if line.startswith('Library=') else line
                          for line in addon.splitlines()) + '\n'
        write(data / 'fcitx5/addon/voiceinput.conf', addon)
    wrapper = home / '.local/bin/fcitx5-voice'
    write(wrapper, '#!/bin/sh\nexec env ' + shlex.quote('PYTHONPATH=' + str(source)) + ' '
          + shlex.quote(str(python)) + ' -m fcitx5_voice "$@"\n', 0o755)
    exec_path = json.dumps(str(wrapper), ensure_ascii=False).replace('%', '%%').replace('$', '$$')
    package_condition = ('ConditionPathExists=/usr/share/fcitx5-voice/PACKAGE_VERSION\n'
                         if args.package_managed else '')
    write(config / 'systemd/user/fcitx5-voice.service',
          '[Unit]\n' + package_condition + 'Description=Fcitx5 local voice recognition\nAfter=graphical-session.target\n'
          'PartOf=graphical-session.target\n\n[Service]\nType=simple\n'
          f'ExecStart={exec_path} serve\nRestart=on-failure\nRestartSec=3\n'
          'TimeoutStopSec=10\nUMask=0077\n\n[Install]\nWantedBy=default.target\n')
    config_file = config / 'fcitx5-voice/config.toml'
    if not config_file.exists():
        config_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / 'config.example.toml', config_file)
    state.mkdir(parents=True, exist_ok=True)
    old_files = set(previous['files'])
    if args.service_only:
        for obsolete in (data / 'fcitx5/addon/voiceinput.conf', library_dir / 'voiceinput.so'):
            if str(obsolete) in old_files:
                obsolete.unlink(missing_ok=True)
                old_files.remove(str(obsolete))
    manifest.write_text(json.dumps({'files': sorted(old_files | set(files)),
                                   'directories': sorted(set(previous['directories']) | set(managed))},
                                  ensure_ascii=False, indent=2))
    print(f'已安装：{wrapper}')
    if not args.quiet:
        print('下载模型后运行：systemctl --user daemon-reload && systemctl --user enable --now fcitx5-voice')
        print('重启 Fcitx5 后，在文本输入框按 Ctrl+Alt+V 开始／结束；流式模式自动分句提交，Esc 放弃未提交部分。')


if __name__ == '__main__':
    main()
