# Streaming Voice Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development for the independent model adapter task; integrate capture, protocol and UI in the current session with test-driven-development.

**Goal:** Display revisable dictation at the focused caret and commit finalized sentences while recording.

**Architecture:** Existing private Unix socket links a Python streaming worker to the Fcitx5 addon. Audio, recognition and UI retain separate ownership; session/segment/sequence guards suppress stale writes.

**Tech Stack:** Python 3.11, asyncio, GStreamer, sherpa-onnx 1.13.7, C++20/Fcitx5 5.1.19.

**Spec:** `docs/superpowers/specs/2026-09-10-streaming-voice-design.md`

## Global Constraints

- Local CPU inference, 16 kHz mono PCM16, no recorded audio or text logging.
- Preserve offline protocol 1 and existing tests; streaming protocol 2.
- Current approved feature branch is `codex/fcitx5-voice`; keep existing workspace and dependencies.

### Task 1: Streaming model and reproducible download

Files: recognizer.py, new streaming_recognizer.py/model_manifest.py, config.py, cli.py, scripts/download-model.py, config.example.toml, tests/test_recognizer.py, tests/test_config.py, new tests/test_streaming_recognizer.py and downloader tests.

Interface: `StreamingRecognizer(config).create_decoder()` returns an object with `accept(pcm: bytes) -> list[tuple[str,str]]`, `finish() -> list[tuple[str,str]]`. Load weights once. `Config.backend` selects streaming/offline, `streaming_model_dir` is distinct from legacy `model_dir`.

- [x] Add tests for revision/endpoint deduplication, final tail and mode/config validation; demonstrate red.
- [x] Implement persistent online decoding, bounded per-sentence length and pinned model download. Example expected event sequence: `[('partial','明天'), ('final','明天下午')]`.
- [x] Wire CLI server selection using `VoiceServer(..., streaming=True)` and file transcribe mode; verify with public WAV and report measured output/timing.

### Task 2: Capture and streaming session lifecycle

Files: audio.py, new streaming_session.py, server.py, new tests/test_streaming_session.py; extend test_audio.py and test_server.py.

Interface: `GStreamerCapture(..., streaming=True).chunks()` yields PCM bytes while active; `stop()` seals/drains queue, `cancel()` discards queue. `StreamingSession` has the same start/stop/cancel/close methods as legacy Session. Server takes `streaming=False` default for compatibility; CLI opts in.

- [x] Add failing tests: receive partial before stop; stop flushes final; cancel during blocked inference discards late partial/final; overflow/natural capture exit fails explicitly.
- [x] Implement bounded capture queue and single-worker async loop using `await asyncio.to_thread(decoder.accept, pcm)`. Stamp segment/seq on emitted events, normalize control characters, finish once after drain.
- [x] Verify real Unix socket start → partial → final → finished, wrong IDs, timeout and disconnect cleanup with deterministic audio/decoder fixtures.

### Task 3: Fcitx5 streaming composition and commits

Files: plugin/session.h/cpp, voiceinput.cpp, tests/plugin_state_test.cpp, tests/plugin_integration_test.cpp.

Interface: `Session::streaming()`, `Session::takeCommit()` plus existing `preview()`; protocol 2 accepts partial/final while Recording/Stopping/Transcribing. `final` sets one pending commit, advances segment, clears preview; `finished` transitions idle.

- [x] Add failing state tests for partial replacement, duplicate final, stale segment/seq, empty final and finished.
- [x] Add real-context fixture tests for embedded preedit, fallback panel, final commits before stop, stop tail and cancellation with late messages.
- [x] Implement UI main-loop delivery, clear preedit before commit, retain legacy preview behavior. Run CTest.

### Task 4: Integration, docs and release verification

Files: README.md, docs/validation.md, package metadata as needed.

- [x] Run `.venv/bin/python -m unittest discover -s tests -v` with PYTHONPATH=src; build and CTest with `.venv/bin/cmake`/ctest.
- [x] Run public WAV through actual streaming model and service, prove partial-before-stop and no duplicate final without accessing microphone.
- [x] Review combined diff for audio/cancellation/focus races; fix regressions and rerun affected checks.
- [x] Document model setup/migration, exact shortcuts and limits, measured validation.
- [x] Commit and push approved development branch to existing .160 origin; retain main until integration is requested.
