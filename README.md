# LiltKey

**Offline voice typing for Linux and Fcitx5.**

English · [简体中文](README.zh-CN.md)

[Website](https://tangzk.github.io/liltkey/) · [License](LICENSE)

Hold `Ctrl+Alt` to talk and release to finish; text appears at the cursor as you speak. Chinese–English mixed dictation and automatic punctuation are supported. Recognition runs on your machine, recordings are never uploaded, and your existing pinyin input keeps working.

![LiltKey light theme: the Fcitx5 pinyin candidate panel](docs/assets/fcitx5-light-theme.png)

*Screenshot of the real Fcitx5 candidate panel in an X11 test text box; voice status uses the same theme.*

> The interface (status messages, notifications, setup prompts) and the detailed docs are currently in Chinese only.

## New in v0.4.0

- Hold `Ctrl+Alt` for about 300 ms to start recording; release either key to stop and commit the last sentence.
- Keep talking for several sentences while holding, with no default 30-second limit. A short press, or pressing another key right after, does not start recording.
- `Ctrl+Alt+V` still toggles recording on and off, and `Esc` still discards uncommitted text.
- The package updates both the native plugin and the recognition service, so upgrading from an older version just works.

## Install

For Ubuntu 26.04 (amd64). Download the [.deb package](https://github.com/tangzk/liltkey/releases/download/v0.4.0/fcitx5-voice_0.4.0_amd64.deb) and install it with the Software app, or run:

```bash
sudo apt install ./fcitx5-voice_0.4.0_amd64.deb
```

The package includes a light theme that is enabled on first setup; existing custom themes, dark preferences and fonts are kept. Default configuration happens automatically after install, with no extra commands. On first run, stay online while about 260 MiB of models download, wait for the “语音输入已就绪” (Voice input is ready) notification, then log out and log back in.

Installation sets Fcitx5 as the default input method and restarts it, keeping your existing pinyin and voice settings. Finish anything you're typing first. Release notes and checksums are on [GitHub Releases](https://github.com/tangzk/liltkey/releases/tag/v0.4.0).

## Usage

In any text box that uses Fcitx5:

| Action | Shortcut |
|---|---|
| Hold to record, release to finish | Hold `Ctrl+Alt` (about 300 ms) |
| Toggle recording on/off | `Ctrl+Alt+V` |
| Discard uncommitted text | `Esc` |

The system microphone is used by default. Text is punctuated and committed when you pause. Holding `Ctrl+Alt` records continuously; releasing either key stops and processes the last sentence. A short press, or pressing another key right after, does not start recording. `Ctrl+Alt+V` still toggles recording, with a 30-second limit per recording in that mode. Committed text is kept.

## More docs (Chinese)

- [Advanced usage and maintenance](docs/advanced-usage.md): microphone, recognition modes, troubleshooting, upgrade and uninstall.
- [Development guide](docs/development.md): build from source, build the deb, tests and upstream projects.
- [Theme and restore](themes/README.md): default theme, switching appearance and restoring your previous settings.
- [Validation notes](docs/validation.md): test results and known limitations.

Original code is licensed under [MIT](LICENSE); third-party software and models keep their own licenses. See [third-party notices](THIRD_PARTY_NOTICES.md) and [model licenses](MODEL_LICENSES.md).
