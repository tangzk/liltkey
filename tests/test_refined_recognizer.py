"""Audio boundaries and fallback behavior for streaming preview + final correction."""
import unittest


BLOCK = b'\x00\x10' * 1600  # 100 ms PCM16, audible, no real model needed.


class Preview:
    def __init__(self, events=()):
        self.events = list(events)
        self.created = 0

    def create_decoder(self):
        owner = self
        owner.created += 1

        class Decoder:
            def accept(self, pcm):
                return owner.events.pop(0) if owner.events else []

            def finish(self):
                return [('final', '松键草稿')]

        return Decoder()


class RefinedRecognizerTests(unittest.TestCase):
    def make(self, preview=None, correct=None, fallback=None):
        from fcitx5_voice.refined_recognizer import RefinedStreamingRecognizer
        self.seen = []

        def refine(pcm):
            self.seen.append(pcm)
            return correct(pcm) if correct else '校正后的文字。'

        return RefinedStreamingRecognizer(preview or Preview(), refine, fallback).create_decoder()

    def test_partials_stay_live_and_audio_is_corrected_only_at_final(self):
        decoder = self.make(Preview([[('partial', '盖甲')]]))
        self.assertEqual(decoder.accept(BLOCK), [('partial', '盖甲')])
        self.assertEqual(self.seen, [])
        self.assertEqual(decoder.finish(), [('final', '校正后的文字。')])
        self.assertEqual(self.seen, [BLOCK])
        self.assertEqual(decoder.finish(), [])

    def test_endpoint_and_stop_use_disjoint_audio_without_tail_padding(self):
        second = b'\x00\x20' * 1600
        preview = Preview([[('final', '第一句'), ('partial', '模型预读草稿')], []])
        decoder = self.make(preview)
        self.assertEqual(decoder.accept(BLOCK), [('final', '校正后的文字。')])
        decoder.accept(second)
        self.assertEqual(decoder.finish(), [('final', '校正后的文字。')])
        self.assertEqual(self.seen, [BLOCK, second])
        self.assertEqual(preview.created, 2)

    def test_corrects_audio_even_when_preview_is_empty(self):
        decoder = self.make(Preview())
        self.assertEqual(decoder.accept(BLOCK), [])
        self.assertEqual(decoder.finish(), [('final', '校正后的文字。')])

    def test_long_continuous_input_is_bounded_and_every_sample_used_once(self):
        decoder = self.make(Preview())
        first = BLOCK * 200  # 20 seconds, even if the preview never finds speech.
        self.assertEqual(decoder.accept(first), [('final', '校正后的文字。')])
        self.assertEqual(self.seen, [first])
        self.assertEqual(decoder.accept(BLOCK), [])
        decoder.finish()
        self.assertEqual(self.seen, [first, BLOCK])

    def test_success_uses_native_punctuation_and_never_runs_fallback_punctuation(self):
        def forbidden(text):
            raise AssertionError('Should not punctuate corrected text twice')
        decoder = self.make(fallback=forbidden, correct=lambda _: '使用Linux。')
        decoder.accept(BLOCK)
        self.assertEqual(decoder.finish(), [('final', '使用 Linux。')])

    def test_failed_empty_or_invalid_correction_keeps_final_preview(self):
        def fail(_):
            raise RuntimeError('private recognized words must not be logged')
        for correct in [fail, lambda _: '', lambda _: None, lambda _: '\x00\x7f', lambda _: 'x' * 8193]:
            with self.subTest(correct=correct):
                decoder = self.make(correct=correct, fallback=lambda text: text + '！')
                decoder.accept(BLOCK)
                self.assertEqual(decoder.finish(), [('final', '松键草稿！')])

    def test_short_audio_skips_corrector_but_preserves_preview(self):
        decoder = self.make(Preview([[('partial', '短句')]]))
        decoder.accept(BLOCK[:100])
        self.assertEqual(decoder.finish(), [('final', '松键草稿')])
        self.assertEqual(self.seen, [])

    def test_silence_does_not_invoke_corrector(self):
        decoder = self.make()
        decoder.accept(b'\x00\x00' * 1600)
        decoder.finish()
        self.assertEqual(self.seen, [])

    def test_empty_stream_and_repeated_finish_emit_nothing(self):
        decoder = self.make()
        self.assertEqual(decoder.finish(), [])
        self.assertEqual(decoder.finish(), [])
        self.assertEqual(self.seen, [])

    def test_rejects_odd_samples_and_input_after_finish(self):
        decoder = self.make()
        with self.assertRaises(ValueError):
            decoder.accept(b'\x00')
        decoder.finish()
        with self.assertRaises(RuntimeError):
            decoder.accept(BLOCK)

    def test_unaligned_capture_chunks_never_exceed_buffer_limit_or_duplicate_pcm(self):
        decoder = self.make(Preview())
        short = b'\x00\x10' * 37
        decoder.accept(short)
        decoder.accept(BLOCK * 201)
        decoder.finish()
        self.assertEqual(b''.join(self.seen), short + BLOCK * 201)
        self.assertEqual([len(x) for x in self.seen], [640000, 3274])

    def test_failed_endpoint_correction_preserves_lookahead_and_native_stream(self):
        preview = Preview([[('partial', '第一'), ('final', '第一句'), ('partial', '第二句')],
                           [('partial', '第二句继续')]])
        def fail(_):
            raise RuntimeError('unavailable')
        decoder = self.make(preview, correct=fail)
        self.assertEqual(decoder.accept(BLOCK), [('partial', '第一'), ('final', '第一句'),
                                                ('partial', '第二句')])
        self.assertEqual(decoder.accept(BLOCK), [('partial', '第二句继续')])
        self.assertEqual(decoder.finish(), [('final', '松键草稿')])
        self.assertEqual(preview.created, 1)
        self.assertEqual(self.seen, [BLOCK])

    def test_failed_hard_boundary_flushes_before_switching_to_plain_streaming(self):
        def fail(_):
            raise RuntimeError('unavailable')
        decoder = self.make(correct=fail)
        self.assertEqual(decoder.accept(BLOCK * 200), [('final', '松键草稿')])
        decoder.accept(BLOCK)
        self.assertEqual(decoder.finish(), [('final', '松键草稿')])
        self.assertEqual(len(self.seen), 1)
