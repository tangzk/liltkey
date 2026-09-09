#!/usr/bin/env python3
"""Download pinned upstream weights, verify SHA256, then atomically publish."""

import argparse
import hashlib
import os
from pathlib import Path
import urllib.request

REVISION = '2365baeacb507f821a0c8120fcee3d484dba7a07'
REPOSITORY = 'csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17'
FILES = {
    'model.int8.onnx': 'c71f0ce00bec95b07744e116345e33d8cbbe08cef896382cf907bf4b51a2cd51',
    'tokens.txt': 'f449eb28dc567533d7fa59be34e2abca8784f771850c78a47fb731a31429a1dc',
}


def digest(path):
    checksum = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            checksum.update(chunk)
    return checksum.hexdigest()


def download(destination, base='https://huggingface.co'):
    destination.mkdir(parents=True, exist_ok=True)
    for filename, checksum in FILES.items():
        target = destination / filename
        if target.exists() and digest(target) == checksum:
            print(f'已校验：{target}', flush=True)
            continue
        url = f'{base.rstrip("/")}/{REPOSITORY}/resolve/{REVISION}/{filename}'
        temporary = target.with_suffix(target.suffix + f'.{os.getpid()}.part')
        try:
            print(f'下载：{filename}', flush=True)
            with urllib.request.urlopen(url, timeout=60) as response, temporary.open('wb') as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
            if digest(temporary) != checksum:
                raise ValueError(f'{filename} 校验失败，请重试')
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    print('离线模型已就绪。后续识别无需联网。')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    default = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'fcitx5-voice/sensevoice'
    parser.add_argument('--dest', type=Path, default=default)
    parser.add_argument('--base-url', default='https://huggingface.co', help='下载站点；SHA256 校验保持不变')
    args = parser.parse_args()
    download(args.dest.expanduser(), args.base_url)


if __name__ == '__main__':
    main()
