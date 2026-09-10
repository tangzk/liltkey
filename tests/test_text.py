import unittest

from fcitx5_voice.text import finalize_text, format_segment


class FinalTextTests(unittest.TestCase):
    def test_chinese_punctuation_removes_unwanted_spaces(self):
        self.assertEqual(finalize_text('今 天 天气不错 ， 我们出去走走 。'),
                         '今天天气不错，我们出去走走。')

    def test_english_punctuation_spacing_preserves_decimal_and_contraction(self):
        self.assertEqual(finalize_text("hello,world! It's 3.14,not 2.0 ."),
                         "hello, world! It's 3.14, not 2.0.")

    def test_mixed_text_has_readable_boundaries_without_splitting_chinese_quantities(self):
        self.assertEqual(finalize_text('使用Linux系统和Python3开发下午3点开会'),
                         '使用 Linux 系统和 Python3 开发下午3点开会')
        self.assertEqual(finalize_text('你好 hello world ，今天不错。'),
                         '你好 hello world，今天不错。')

    def test_punctuation_is_applied_once_to_nonempty_segment(self):
        seen = []

        def punctuate(text):
            seen.append(text)
            return '今天天气不错，我们出去走走吧。'

        self.assertEqual(finalize_text('今天天气不错我们出去走走吧', punctuate),
                         '今天天气不错，我们出去走走吧。')
        self.assertEqual(finalize_text('', punctuate), '')
        self.assertEqual(seen, ['今天天气不错我们出去走走吧'])

    def test_failed_punctuation_keeps_original_words_and_sanitizes_controls(self):
        def broken(text):
            raise RuntimeError('inference failed')

        self.assertEqual(finalize_text('使用Linux\n系统\x7f', broken), '使用 Linux 系统')
        self.assertEqual(finalize_text('保留文字', lambda text: ''), '保留文字')

    def test_oversized_input_is_rejected_and_oversized_model_output_falls_back(self):
        with self.assertRaises(ValueError):
            finalize_text('字' * 3000)
        self.assertEqual(finalize_text('原文', lambda text: '字' * 3000), '原文')

    def test_partial_format_remains_unpunctuated(self):
        self.assertEqual(format_segment('使用Linux系统'), '使用Linux系统')
        self.assertEqual(format_segment('how are you', '?'), ' how are you')

    def test_numeric_grouping_and_url_queries_are_not_split(self):
        self.assertEqual(finalize_text('1,000 dollars,not 2,000'), '1,000 dollars, not 2,000')
        self.assertEqual(finalize_text('https://example.com?q=one'), 'https://example.com?q=one')
        self.assertEqual(finalize_text('访问https://example.com?a=1;b=2 网站'),
                         '访问 https://example.com?a=1;b=2 网站')

    def test_unicode_urls_are_preserved(self):
        for text in ['https://example.com/中文?q=one', 'https://例子.测试?q=one']:
            self.assertEqual(finalize_text(text), text)
