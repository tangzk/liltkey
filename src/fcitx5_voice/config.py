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
    model_dir: Path = field(default_factory=lambda: data_dir() / 'sensevoice')
    threads: int = 4
    max_seconds: int = 30
    device: str = ''
    language: str = 'auto'


def load_config(path=None):
    explicit = path is not None
    path = Path(path) if explicit else config_path()
    if not path.exists() and not explicit:
        return Config()
    with path.open('rb') as handle:
        data = tomllib.load(handle)
    unknown = set(data) - set(Config.__dataclass_fields__)
    if unknown:
        raise ValueError('未知配置项：' + ', '.join(sorted(unknown)))
    for key, minimum, maximum in [('threads', 1, 16), ('max_seconds', 1, 30)]:
        value = data.get(key, getattr(Config(), key))
        if type(value) is not int or not minimum <= value <= maximum:
            raise ValueError(f'{key} 必须是 {minimum}～{maximum} 之间的整数')
    for key in ['model_dir', 'device', 'language']:
        if key in data and not isinstance(data[key], str):
            raise ValueError(f'{key} 必须是字符串')
    if data.get('language', 'auto') not in {'auto', 'zh', 'en', 'ja', 'ko', 'yue'}:
        raise ValueError('language 必须是 auto/zh/en/ja/ko/yue')
    if any(ord(c) < 32 for c in data.get('device', '')):
        raise ValueError('device 不能包含控制字符')
    if 'model_dir' in data:
        data['model_dir'] = Path(data['model_dir']).expanduser()
        if not data['model_dir'].is_absolute():
            data['model_dir'] = (path.parent / data['model_dir']).resolve()
    return Config(**data)
