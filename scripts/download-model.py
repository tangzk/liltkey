#!/usr/bin/env python3
"""Download pinned upstream weights, verify SHA256, then atomically publish."""

import argparse
import hashlib
import os
from pathlib import Path
import sys
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from fcitx5_voice.model_manifest import (  # noqa: E402
    MODELS, OFFLINE_MODEL, PUNCTUATION_MODEL, STREAMING_MODEL,
)


def digest(path):
    checksum = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            checksum.update(chunk)
    return checksum.hexdigest()


def download(destination, manifest=STREAMING_MODEL, base=None):
    destination.mkdir(parents=True, exist_ok=True)
    for item in manifest.files:
        target = destination / item.name
        if target.exists() and digest(target) == item.sha256:
            print(f'已校验：{target}', flush=True)
            continue
        source = item.source or item.name
        url = (f'{(base or manifest.base_url).rstrip("/")}/{manifest.repository}/'
               f'{"resolve/" if manifest.base_url.endswith("huggingface.co") else ""}'
               f'{manifest.revision}/{source}')
        temporary = target.with_suffix(target.suffix + f'.{os.getpid()}.part')
        extracted = target.with_suffix(target.suffix + f'.{os.getpid()}.extract.part')
        try:
            print(f'下载：{source}', flush=True)
            with urllib.request.urlopen(url, timeout=60) as response, temporary.open('wb') as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
            if digest(temporary) != (item.source_sha256 or item.sha256):
                raise ValueError(f'{source} 校验失败，请重试')
            publish = temporary
            if item.archive_member:
                with tarfile.open(temporary, 'r:*') as archive:
                    member = archive.getmember(item.archive_member)
                    if not member.isfile():
                        raise ValueError(f'{source} 中的模型文件无效')
                    stream = archive.extractfile(member)
                    if stream is None:
                        raise ValueError(f'{source} 中缺少模型文件')
                    with stream, extracted.open('wb') as output:
                        while chunk := stream.read(1024 * 1024):
                            output.write(chunk)
                publish = extracted
            if digest(publish) != item.sha256:
                raise ValueError(f'{item.name} 校验失败，请重试')
            publish.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
            extracted.unlink(missing_ok=True)
    print(f'{manifest.directory} 模型已就绪。后续识别无需联网。')


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', choices=MODELS, default='streaming')
    parser.add_argument('--dest', type=Path)
    parser.add_argument('--base-url', help='覆盖下载站点；SHA256 校验保持不变')
    refinement = parser.add_mutually_exclusive_group()
    refinement.add_argument('--with-refinement', action='store_true', default=True,
                            help='同时下载 SenseVoice 定稿校正模型（默认开启）')
    refinement.add_argument('--no-refinement', dest='with_refinement', action='store_false',
                            help='不下载 SenseVoice 定稿校正模型')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--punctuation-only', action='store_true')
    mode.add_argument('--no-punctuation', action='store_true')
    return parser.parse_args(argv)


def selected_manifests(args):
    if args.punctuation_only:
        return (PUNCTUATION_MODEL,)
    if args.backend == 'offline':
        return (OFFLINE_MODEL,)
    manifests = (STREAMING_MODEL, OFFLINE_MODEL) if args.with_refinement else (STREAMING_MODEL,)
    return manifests if args.no_punctuation else (*manifests, PUNCTUATION_MODEL)


def main(argv=None):
    args = parse_args(argv)
    manifests = selected_manifests(args)
    root = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'fcitx5-voice'
    for index, manifest in enumerate(manifests):
        destination = args.dest if index == 0 and args.dest else root / manifest.directory
        download(destination.expanduser(), manifest, args.base_url)


if __name__ == '__main__':
    main()
