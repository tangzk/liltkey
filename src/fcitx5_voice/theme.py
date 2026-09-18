"""Install theme assets and apply first-use defaults without resetting preferences."""

import json
from pathlib import Path
import re
import stat
import tempfile

THEME = 'liltkey-light'


def atomic_write(path: Path, content: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.' + path.name,
                                     delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(content)
    try:
        temporary.chmod(mode)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def install_theme(root: Path, data: Path, config: Path):
    source = root / 'themes' / THEME
    # Keep a user copy so removing the deb cannot leave a selected theme missing.
    for path in source.iterdir():
        if path.is_file():
            atomic_write(data / 'fcitx5/themes' / THEME / path.name, path.read_bytes())

    state = data / 'fcitx5-voice'
    marker = state / 'theme-default.json'
    if marker.exists():
        return  # Later choices, including selecting "default", belong to the user.

    classic = config / 'fcitx5/conf/classicui.conf'
    original = classic.read_bytes() if classic.exists() else None
    text = original.decode('utf-8') if original is not None else ''
    lines = text.splitlines(keepends=True)
    values, positions = {}, {}
    section_start = len(lines)
    for index, line in enumerate(lines):
        if line.lstrip().startswith('['):
            section_start = index
            break
        match = re.match(r'^\s*([^#;=\s][^=]*?)\s*=(.*)$', line.rstrip('\r\n'))
        if match:
            key, value = match.groups()
            values[key] = value.strip().strip('"')
            positions.setdefault(key, []).append(index)

    enable = (values.get('Theme', 'default') in {'default', THEME}
              and values.get('UseDarkTheme', 'False').lower() != 'true')
    if enable:
        if original is not None:
            backup = state / 'theme-backup/classicui.conf'
            if not backup.exists():
                atomic_write(backup, original)
                backup.chmod(stat.S_IMODE(classic.stat().st_mode))
        updates = {'Theme': THEME, 'UseDarkTheme': 'False', 'UseAccentColor': 'False'}
        for key, value in {'Font': '"Noto Sans CJK SC Medium 13"',
                           'MenuFont': '"Noto Sans CJK SC 11"'}.items():
            if values.get(key, 'Sans 10') == 'Sans 10':
                updates[key] = value
        if 'Vertical Candidate List' not in values:
            updates['Vertical Candidate List'] = 'False'
        extra = []
        for key, value in updates.items():
            replacement = f'{key}={value}\n'
            if key in positions:
                for index in positions[key]:
                    lines[index] = replacement
            else:
                extra.append(replacement)
        if section_start and not lines[section_start - 1].endswith('\n'):
            lines[section_start - 1] += '\n'
        lines[section_start:section_start] = extra
        atomic_write(classic, ''.join(lines).encode('utf-8'))
    atomic_write(marker, json.dumps({'version': 1, 'applied': enable}).encode('utf-8'))
