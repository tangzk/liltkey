"""Normalize recognizer segments consistently for live and file transcription."""

import logging
import re


_HAN = r'\u3400-\u9fff\uf900-\ufaff\U00020000-\U0003134f'


def format_segment(text, committed_tail='', mixed_spacing=False):
    text = ''.join(' ' if character.isspace() else character for character in text
                   if ((ord(character) >= 32 and ord(character) != 127)
                       or character.isspace())).strip()
    english_boundary = (committed_tail and text and committed_tail.isascii()
            and (committed_tail.isalnum() or committed_tail in '.!?;:,')
            and text[0].isascii() and text[0].isalnum())
    mixed_boundary = (mixed_spacing and committed_tail and text and (
        (re.fullmatch(f'[{_HAN}]', committed_tail) and text[0].isascii() and text[0].isalpha())
        or (committed_tail.isascii() and committed_tail.isalpha()
            and re.fullmatch(f'[{_HAN}]', text[0]))))
    if english_boundary or mixed_boundary:
        text = ' ' + text
    if len(text.encode('utf-8')) > 8192:
        raise ValueError('单句识别结果过长，请分成短句输入')
    return text


def finalize_text(text, punctuate=None):
    """Restore one final only; failed optional punctuation never discards speech."""
    text = format_segment(text)
    if not text:
        return ''
    if punctuate is not None:
        try:
            restored = format_segment(punctuate(text))
            if not restored:
                raise ValueError('empty punctuation output')
            text = restored
        except Exception:
            # Do not log the exception: third-party errors can contain spoken text.
            logging.getLogger(__name__).warning('标点处理失败，已保留原始识别文字')
    text = re.sub(r' +', ' ', text)
    # Protect URL syntax; '?' and ';' can be part of a query, not prose.
    parts = re.split(f'((?:[A-Za-z][A-Za-z0-9+.-]*://|www\\.)'
                     r'[^\s，。！？；：、]+)', text)
    for index in range(len(parts)):
        if index % 2:
            if parts[index - 1] and re.fullmatch(f'[{_HAN}]', parts[index - 1][-1]):
                parts[index] = ' ' + parts[index]
            if index + 1 < len(parts) and parts[index + 1] and re.fullmatch(f'[{_HAN}]', parts[index + 1][0]):
                parts[index] += ' '
            continue
        part = re.sub(f'(?<=[{_HAN}]) +(?=[{_HAN}])', '', parts[index])
        part = re.sub(r' *([，。！？；：、]) *', r'\1', part)
        part = re.sub(r' +([,.!?;:])', r'\1', part)
        part = re.sub(r'([!?;]) *(?=[A-Za-z0-9])', r'\1 ', part)
        # A comma between digits may be a thousands separator; retain it.
        part = re.sub(r'(?<![0-9]), *(?=[A-Za-z0-9])', ', ', part)
        part = re.sub(r', *(?=[A-Za-z])', ', ', part)
        # Keep decimal points, contractions, version strings and URLs intact.
        part = re.sub(f'(?<=[{_HAN}])(?=[A-Za-z])', ' ', part)
        parts[index] = re.sub(f'([A-Za-z][A-Za-z0-9]*)(?=[{_HAN}])', r'\1 ', part)
    return format_segment(''.join(parts))
