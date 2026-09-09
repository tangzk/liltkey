# Fcitx5 Voice Implementation Plan

> For agentic workers: use superpowers:subagent-driven-development for the independent plugin task and review. Use tests before behavior changes.

**Goal:** Deliver an installable offline voice addon that coexists with Fcitx5 Pinyin.

**Architecture:** A lightweight Fcitx5 Module communicates over JSONL Unix Socket with a preloaded Python SenseVoice service. GStreamer records bounded PCM in memory. Preview requires explicit Enter before committing.

**Tech Stack:** C++20, Fcitx5 Core/Config/Utils, json-c, Python 3.11+, GStreamer, sherpa-onnx, CMake, unittest.

**Spec:** `docs/superpowers/specs/2026-09-09-fcitx5-voice-design.md`

## Global Constraints

- Match protocol v1 from the spec; use session IDs to reject stale results.
- No microphone access before a user start action; no transcript logging.
- Do not block the Fcitx5 event loop or commit after focus changes.
- Use the existing empty project on branch codex/fcitx5-voice; no existing user code requires a separate checkout.

## Task 1: Service state, capture and recognition

Files: `src/fcitx5_voice/{session,server,audio,recognizer,config,cli}.py`, `pyproject.toml`, `tests/test_session.py`, `tests/test_server.py`, `tests/test_config.py`.

Interfaces: `Session.start(id)`, `Session.stop(id)`, `Session.cancel(id)`, `Session.close()` async methods; async `emit(dict)` callback. Capture factory returns object with `start()`, `stop() -> bytes`, `cancel()` async methods. Recognizer accepts PCM bytes and returns text synchronously in a worker thread. Server exposes protocol v1.

- [x] Write tests for start/stop/result, no-speech, cancel-during-inference, mismatched IDs, duplicate start, disconnect, oversized input and socket permissions. Representative expectation: after cancel, completing inference must never emit `{"type":"result","id":"old","text":"旧结果"}`.
- [x] Run `python3 -m unittest discover -s tests -v`; confirm missing service behavior fails.
- [x] Implement bounded recording, independent inference worker and JSONL server; add TOML validation and CLI `serve`, `doctor`, `transcribe`, `devices`.
- [x] Repeat unittest and real socket integration tests. Run genuine model transcription on a public fixture.

## Task 2: Fcitx5 Module

Files: `CMakeLists.txt`, `plugin/*`, `tests/plugin*`.

Consumes protocol v1. Produces `voiceinput.so` with Module registration `voiceinput.conf`. Hotkey Ctrl+Alt+v toggles record/stop. Escape cancels; Enter commits preview. Configuration exposes hotkey.

- [x] Write C++ session/UTF-8/protocol tests demonstrating stale IDs and invalid phase cannot commit. Use literal UTF-8 example `你好Ubuntu` and verify one backspace produces `你好Ubunt`.
- [x] Build tests to confirm missing behavior, then implement nonblocking IPC and input-context-bound plugin.
- [x] Run CTest and a headless Fcitx5 integration test, checking actual commitString output, focus cancellation and unhandled ordinary keys.

## Task 3: Install, packaging and review

Files: `scripts/*`, `packaging/*`, `README.md`, config sample.

Consumes compiled module and Python entrypoint. Installs to user-owned paths and supports an isolated verification directory. Never replaces unrelated Fcitx configuration.

- [x] Add reproducible setup/build instructions, model download validation, user-level install and uninstall, systemd service and Debian package builder.
- [x] Run install/uninstall against temporary HOME/XDG directories and inspect packaged files with `dpkg-deb --contents`.
- [x] Run all tests, compile, public sample recognition, and independent final review. Fix concrete failures and document validation limits.
