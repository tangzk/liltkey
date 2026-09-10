"""Local CPU punctuation restoration for final recognition segments."""

import re
import threading
import unicodedata

from .config import Config


MAX_TEXT_BYTES = 8192
_PROTECTED_ASCII = re.compile(
    r"(?:[A-Za-z][A-Za-z0-9+.-]*://|www\.)\S+"
    r"|\d+(?:[.,]\d+)+"
    r"|[A-Za-z]+(?:['’][A-Za-z]+)+")


def _is_punctuation(character: str) -> bool:
    return unicodedata.category(character).startswith('P')


def _is_ascii_word(character: str) -> bool:
    return character.isascii() and (character.isalnum() or character == '_')


def _preserves_content(original: str, result: str) -> bool:
    """Allow inserted punctuation/spacing while retaining every original character."""
    expected = [(index, character) for index, character in enumerate(original)
                if not character.isspace()]
    matched = []
    expected_index = 0
    for result_index, character in enumerate(result):
        if character.isspace():
            continue
        if expected_index < len(expected) and character == expected[expected_index][1]:
            matched.append(result_index)
            expected_index += 1
        elif not _is_punctuation(character):
            return False
    if expected_index != len(expected):
        return False

    positions = {original_index: result_index
                 for (original_index, _), result_index in zip(expected, matched)}
    for span in _PROTECTED_ASCII.finditer(original):
        if result[positions[span.start()]:positions[span.end() - 1] + 1] != span.group(0):
            return False

    for index in range(len(expected) - 1):
        left_position, left = expected[index]
        right_position, right = expected[index + 1]
        had_boundary = any(character.isspace()
                           for character in original[left_position + 1:right_position])
        if had_boundary and _is_ascii_word(left) and _is_ascii_word(right):
            between = result[matched[index] + 1:matched[index + 1]]
            if not any(character.isspace() or _is_punctuation(character)
                       for character in between):
                return False
    return True


class PunctuationRestorer:
    """Load one CT-Transformer model and serialize calls to its native runtime."""

    def __init__(self, config: Config):
        model = config.punctuation_model_dir / 'model.int8.onnx'
        if not model.is_file():
            raise FileNotFoundError(
                f'标点模型未就绪：{model}。'
                '请运行 scripts/download-model.py --punctuation-only。')
        import sherpa_onnx
        model_config = sherpa_onnx.OfflinePunctuationModelConfig(
            ct_transformer=str(model), num_threads=config.threads, provider='cpu')
        punctuation_config = sherpa_onnx.OfflinePunctuationConfig(model=model_config)
        self.model = sherpa_onnx.OfflinePunctuation(punctuation_config)
        self.lock = threading.Lock()

    def __call__(self, text: str) -> str:
        if not text or text.isspace():
            return text
        if len(text.encode('utf-8')) > MAX_TEXT_BYTES:
            raise ValueError('标点输入过长，请分成短句输入')
        with self.lock:
            result = self.model.add_punctuation(text)
        if not isinstance(result, str):
            raise TypeError('标点模型返回了非文本结果')
        if len(result.encode('utf-8')) > MAX_TEXT_BYTES:
            raise ValueError('标点输出过长，请分成短句输入')
        if not _preserves_content(text, result):
            raise ValueError('标点模型改变了识别内容')
        return result
