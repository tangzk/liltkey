#!/usr/bin/env python3
"""Download pinned upstream weights, verify SHA256, then atomically publish."""

import argparse
import hashlib
import os
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from fcitx5_voice.model_manifest import MODELS, STREAMING_MODEL  # noqa: E402


def digest(path):
    checksum = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            checksum.update(chunk)
    return checksum.hexdigest()


def download(destination, manifest=STREAMING_MODEL, base='https://huggingface.co'):
    destination.mkdir(parents=True, exist_ok=True)
    for item in manifest.files:
        target = destination / item.name
        if target.exists() and digest(target) == item.sha256:
            print(f'已校验：{target}', flush=True)
            continue
        url = (f'{base.rstrip("/")}/{manifest.repository}/resolve/'
               f'{manifest.revision}/{item.name}')
        temporary = target.with_suffix(target.suffix + f'.{os.getpid()}.part')
        try:
            print(f'下载：{item.name}', flush=True)
            with urllib.request.urlopen(url, timeout=60) as response, temporary.open('wb') as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
            if digest(temporary) != item.sha256:
                raise ValueError(f'{item.name} 校验失败，请重试')
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    print(f'{manifest.directory} 模型已就绪。后续识别无需联网。')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', choices=MODELS, default='streaming')
    parser.add_argument('--dest', type=Path)
    parser.add_argument('--base-url', default='https://huggingface.co', help='下载站点；SHA256 校验保持不变')
    args = parser.parse_args()
    manifest = MODELS[args.backend]
    default = (Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) /
               'fcitx5-voice' / manifest.directory)
    download((args.dest or default).expanduser(), manifest, args.base_url)


if __name__ == '__main__':
    main()
