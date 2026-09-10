"""Small, validated user configuration without optional runtime imports."""

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


def data_dir():
    return Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'fcitx5-voice'


def config_path():
    return Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'fcitx5-voice/config.toml'


def socket_path():
    runtime = os.environ.get('XDG_RUNTIME_DIR')
    if not runtime:
        raise RuntimeError('XDG_RUNTIME_DIR 未设置，请在正常桌面用户会话中启动服务。')
    return Path(runtime) / 'fcitx5-voice/service.sock'


@dataclass(frozen=True)
class Config:
    backend: str = 'streaming'
    model_dir: Path = field(default_factory=lambda: data_dir() / 'sensevoice')
    streaming_model_dir: Path = field(default_factory=lambda: data_dir() /
                                      'streaming-zipformer-bilingual-zh-en-2023-02-20')
    threads: int = 4
    max_seconds: int = 30
    device: str = ''
    language: str = 'auto'


def load_config(path=None, backend=None):
    explicit = path is not None
    path = Path(path) if explicit else config_path()
    if not path.exists() and not explicit:
        return Config(backend=backend or 'streaming')
    with path.open('rb') as handle:
        data = tomllib.load(handle)
    if backend is not None:
        data['backend'] = backend
    unknown = set(data) - set(Config.__dataclass_fields__)
    if unknown:
        raise ValueError('未知配置项：' + ', '.join(sorted(unknown)))
    for key, minimum, maximum in [('threads', 1, 16), ('max_seconds', 1, 30)]:
        value = data.get(key, getattr(Config(), key))
        if type(value) is not int or not minimum <= value <= maximum:
            raise ValueError(f'{key} 必须是 {minimum}～{maximum} 之间的整数')
    for key in ['backend', 'model_dir', 'streaming_model_dir', 'device', 'language']:
        if key in data and not isinstance(data[key], str):
            raise ValueError(f'{key} 必须是字符串')
    if data.get('backend', 'streaming') not in {'streaming', 'offline'}:
        raise ValueError('backend 必须是 streaming/offline')
    if data.get('language', 'auto') not in {'auto', 'zh', 'en', 'ja', 'ko', 'yue'}:
        raise ValueError('language 必须是 auto/zh/en/ja/ko/yue')
    if data.get('backend', 'streaming') == 'streaming' and data.get('language', 'auto') != 'auto':
        raise ValueError('streaming 双语模型自动识别中英文，language 必须是 auto')
    if any(ord(c) < 32 for c in data.get('device', '')):
        raise ValueError('device 不能包含控制字符')
    for key in ('model_dir', 'streaming_model_dir'):
        if key in data:
            data[key] = Path(data[key]).expanduser()
            if not data[key].is_absolute():
                data[key] = (path.parent / data[key]).resolve()
    return Config(**data)
