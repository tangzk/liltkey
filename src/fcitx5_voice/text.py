"""Normalize recognizer segments consistently for live and file transcription."""


def format_segment(text, committed_tail=''):
    text = ''.join(' ' if character.isspace() else character for character in text
                   if ((ord(character) >= 32 and ord(character) != 127)
                       or character.isspace())).strip()
    if (committed_tail and text and committed_tail.isascii()
            and (committed_tail.isalnum() or committed_tail in '.!?;:,')
            and text[0].isascii() and text[0].isalnum()):
        text = ' ' + text
    if len(text.encode('utf-8')) > 8192:
        raise ValueError('单句识别结果过长，请分成短句输入')
    return text
