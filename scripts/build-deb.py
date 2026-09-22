#!/usr/bin/env python3
"""Build an Ubuntu native-addon package with user-scoped Python setup."""

import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_VERSION = '0.5.1'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plugin', type=Path, default=ROOT / 'build/voiceinput.so')
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    if not args.plugin.is_file():
        parser.error('请先编译插件或指定 --plugin')
    architecture = subprocess.check_output(['dpkg', '--print-architecture'], text=True).strip()
    multiarch = subprocess.check_output(['dpkg-architecture', '-qDEB_HOST_MULTIARCH'], text=True).strip()
    args.output.mkdir(parents=True, exist_ok=True)
    output = (args.output / f'fcitx5-voice_{PACKAGE_VERSION}_{architecture}.deb').resolve()
    with tempfile.TemporaryDirectory(prefix='fcitx5-voice-deb-') as temporary:
        stage = Path(temporary)

        def copy(source, destination):
            target = stage / destination
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

        def write(destination, content, mode=0o644):
            target = stage / destination
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
            target.chmod(mode)

        copy(args.plugin, f'usr/lib/{multiarch}/fcitx5/voiceinput.so')
        addon = ((ROOT / 'plugin/voiceinput.conf.in').read_text()
                 .replace('@PROJECT_VERSION@', '0.5.1').replace('@VOICEINPUT_LIBRARY@', 'voiceinput'))
        write('usr/share/fcitx5/addon/voiceinput.conf', addon)
        package_root = stage / 'usr/share/fcitx5-voice'
        for directory in ['src', 'scripts']:
            shutil.copytree(ROOT / directory, package_root / directory,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.egg-info'))
        for filename in ['pyproject.toml', 'config.example.toml', 'README.md', 'README.zh-CN.md']:
            copy(ROOT / filename, f'usr/share/fcitx5-voice/{filename}')
        for document in sorted((ROOT / 'docs').glob('*.md')):
            copy(document, f'usr/share/fcitx5-voice/docs/{document.name}')
        if (ROOT / 'docs/assets').is_dir():
            shutil.copytree(ROOT / 'docs/assets', package_root / 'docs/assets')
        for destination in [stage / 'usr/share/fcitx5/themes/liltkey-light',
                            package_root / 'themes/liltkey-light']:
            shutil.copytree(ROOT / 'themes/liltkey-light', destination)
        copy(ROOT / 'themes/README.md', 'usr/share/fcitx5-voice/themes/README.md')
        for destination in ['usr/share/fcitx5-voice', 'usr/share/doc/fcitx5-voice']:
            for filename in ['LICENSE', 'THIRD_PARTY_NOTICES.md', 'MODEL_LICENSES.md',
                             'packaging/json-c-copyright']:
                copy(ROOT / filename, f'{destination}/{filename}')
            shutil.copytree(ROOT / 'licenses', stage / destination / 'licenses')
        write('usr/share/doc/fcitx5-voice/copyright', (ROOT / 'LICENSE').read_text() +
              '\nThird-party code and model terms are documented in THIRD_PARTY_NOTICES.md\n'
              'and MODEL_LICENSES.md in this directory. See licenses/ and\n'
              'packaging/json-c-copyright for the accompanying license texts.\n')
        copy(ROOT / 'packaging/json-c-copyright', 'usr/share/doc/fcitx5-voice/json-c-copyright')
        write('usr/share/fcitx5-voice/PACKAGE_VERSION', PACKAGE_VERSION + '\n')
        copy(ROOT/'packaging/fcitx5-voice-setup.service', 'usr/lib/systemd/user/fcitx5-voice-setup.service')
        copy(ROOT/'packaging/fcitx5-voice-autosetup.desktop', 'etc/xdg/autostart/fcitx5-voice-autosetup.desktop')
        for hook in ('postinst', 'prerm'):
            write('DEBIAN/' + hook, (ROOT/'packaging'/hook).read_text(), 0o755)
        write('usr/bin/fcitx5-voice-autosetup',
              '#!/bin/sh\nexec python3 /usr/share/fcitx5-voice/scripts/auto-setup.py --launch "$@"\n', 0o755)
        write('usr/bin/fcitx5-voice-setup',
              '#!/bin/sh\nexec python3 /usr/share/fcitx5-voice/scripts/setup.py --service-only "$@"\n', 0o755)
        write('usr/bin/fcitx5-voice-download-model',
              '#!/bin/sh\nexec python3 /usr/share/fcitx5-voice/scripts/download-model.py "$@"\n', 0o755)
        write('usr/bin/fcitx5-voice', '#!/bin/sh\n'
              'runtime="${XDG_DATA_HOME:-$HOME/.local/share}/fcitx5-voice/venv/bin/python"\n'
              'if [ ! -x "$runtime" ]; then\n'
              '  echo "自动配置正在准备运行环境，请保持联网并等待完成通知。" >&2\n'
              '  exit 1\nfi\n'
              'exec env PYTHONPATH=/usr/share/fcitx5-voice/src "$runtime" -m fcitx5_voice "$@"\n', 0o755)
        write('DEBIAN/control', f'Package: fcitx5-voice\nVersion: {PACKAGE_VERSION}\nSection: utils\nPriority: optional\n'
              f'Architecture: {architecture}\nMaintainer: Fcitx5 Voice contributors\n'
              'Depends: fcitx5 (>= 5.1.19), libfcitx5core7, libfcitx5config6, libfcitx5utils2, '
              'libjson-c5, libc6 (>= 2.38), libstdc++6 (>= 13.1), python3 (>= 3.11), python3-venv, im-config, '
              'systemd, dbus-user-session, libnotify-bin, '
              'gstreamer1.0-tools, gstreamer1.0-plugins-base, gstreamer1.0-plugins-good\n'
              'Recommends: fcitx5-frontend-gtk3, fcitx5-frontend-gtk4, fcitx5-frontend-qt5, fcitx5-frontend-qt6, pulseaudio-utils, fonts-noto-cjk\n'
              'Description: Offline voice dictation module for Fcitx5\n'
              ' Native Fcitx5 addon and Python service. Model and Python runtime dependencies\n'
              ' are configured automatically in each desktop user session.\n')
        subprocess.run(['dpkg-deb', '--root-owner-group', '--build', str(stage), str(output)], check=True)
    print(output)


if __name__ == '__main__':
    main()
