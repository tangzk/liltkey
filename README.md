# LiltKey

**以声为键，开口成文。**

*Your voice, your keyboard.*

为 Linux / Fcitx5 打造的本地语音输入工具。边说边输入，中英自然混输，让声音留在本机。

[项目宣传页](https://tangzk.github.io/liltkey/) · [下载安装](#安装推荐) · [使用指南](#使用) · [配置与诊断](#配置与诊断) · [宣传页源码](website/README.md)

> LiltKey 是产品名称；安装包、命令、服务及配置目录沿用 `fcitx5-voice`。

## 项目介绍

Fcitx5 原生模块 + 独立本地识别服务。默认使用中英双语流式 Zipformer：边说边在光标处显示文字，停顿分句后自动写入输入框。保留现有拼音输入及 SenseVoice 离线预览模式；识别在本机 CPU 执行，不上传录音，不保存语音或识别文本日志。

## 使用

在支持 Fcitx5 的文本输入框内：

| 操作 | 按键 |
|---|---|
| 开始录音／结束录音 | `Ctrl+Alt+V` |
| 放弃当前未提交文字并停止 | `Esc` |
| 离线模式提交／删除预览末字 | `Enter` / `Backspace` |

每次录音最多 30 秒，期间可提交多句话。正在识别的文字属于预编辑，可能随上下文修正；停顿后正式提交，录音继续。再次按快捷键会结束录音、处理剩余音频并提交尾句，无须按 Enter。Esc 只放弃当前未提交部分，已提交句子保留。

流式模式默认在定稿前使用本地中英标点模型恢复逗号、句号、问号，并整理空格。临时文字持续显示，标点在分句定稿时出现；中文词间不加空格，中英相邻按“使用 Linux 系统”处理，英文保留词间空格。模型根据当前分句文字预测标点，可能判断不准；不会回改已提交正文。标点推理异常时保留原始文字并继续听写。

改用普通键盘输入、切换窗口或输入框、客户端重置输入状态时会取消本次会话。已有拼音预编辑时先完成或取消拼音；密码和标记为敏感的输入框禁用语音。快捷键通过 Fcitx5 附加组件配置修改。

输入框必须正常接入 Fcitx5。支持客户端预编辑的应用在光标处显示下划线文字；不支持时退回输入法面板预编辑。鼠标在同一输入框移动光标时，能否及时取消取决于应用是否发送 reset 等输入法事件，不能保证任意应用的光标锁定。语音模式下 Enter 属于普通键盘输入，不会代替停止快捷键。

## 安装（推荐）

下载 [v0.3.0 的 `.deb` 安装包](https://github.com/tangzk/liltkey/releases/download/v0.3.0/fcitx5-voice_0.3.0_amd64.deb)，或到 [GitHub Releases](https://github.com/tangzk/liltkey/releases/tag/v0.3.0) 查看版本说明和 `SHA256SUMS`。

此预编译包的验证目标是 **Ubuntu 26.04 / amd64（x86-64）/ Fcitx5 5.1.19**；其他系统或 ARM 设备请自行构建并验证。已安装的 Fcitx5 不应低于 5.1.19。

在下载目录打开终端，运行：

```bash
sudo apt install ./fcitx5-voice_0.3.0_amd64.deb
fcitx5-voice-setup
fcitx5-voice-download-model
fcitx5-voice doctor
systemctl --user daemon-reload
systemctl --user enable --now fcitx5-voice
```

只有 `apt install` 使用 sudo；后续命令使用当前桌面用户执行。最后结束拼音预编辑，从 Fcitx5 托盘菜单重启输入法，再按 `Ctrl+Alt+V` 开始听写。

`.deb` 包含原生插件、服务源码、安装工具及许可声明，**不包含模型和 Python 第三方依赖**。首次运行 setup/download 命令需要联网，不会在安装 `.deb` 时自动下载、启动服务或重启输入法。初始化完成后听写无需联网。

## 从源码安装

目标：Ubuntu 26.04、Fcitx5 5.1.19。其他版本需要在对应系统上重新编译并验证。

安装系统开发依赖：

```bash
sudo apt install git build-essential cmake pkg-config libfcitx5core-dev libfcitx5config-dev libfcitx5utils-dev libjson-c-dev python3-venv gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good
```

构建插件：

```bash
git clone https://github.com/tangzk/liltkey.git
cd liltkey
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j4
ctest --test-dir build --output-on-failure
```

安装用户级插件与服务。若系统已有 `uv`，安装脚本使用独立 Python 3.11 环境；否则使用系统 Python 的 venv。安装依赖和下载模型时需要联网，识别时无需联网。

```bash
python3 scripts/install-user.py
python3 scripts/download-model.py
~/.local/bin/fcitx5-voice doctor
systemctl --user daemon-reload
systemctl --user enable --now fcitx5-voice
```

之后使用 Fcitx5 托盘菜单重启 Fcitx5，或运行 `fcitx5 -rd`。重启前结束正在编辑的拼音预编辑。

用户级安装不会更换默认输入法或改写现有拼音配置。模型固定到上游 revision，并验证 SHA256，下载失败不会替换已可用模型。默认下载流式中英模型，另外需要 Python 运行依赖。SenseVoice 仅在选择离线模式时需要。

## 自行构建 Debian 安装包

构建后执行：

```bash
python3 scripts/build-deb.py
```

产物位于 `dist/fcitx5-voice_0.3.0_<架构>.deb`，按上面的安装步骤操作。发布的预编译包仅验证 Ubuntu 26.04 amd64；在其他平台构建时，需同时核对打包脚本中的运行库依赖。

## 配置与诊断

服务配置：`~/.config/fcitx5-voice/config.toml`，遵守 `XDG_CONFIG_HOME`。参见 [config.example.toml](config.example.toml)。修改后执行 `systemctl --user restart fcitx5-voice`。

```toml
backend = "streaming"
punctuation = true
threads = 4
max_seconds = 30
language = "auto"
device = ""
```

- `device` 为空时使用系统默认麦克风。运行 `fcitx5-voice devices` 查询音频设备；`pactl list short sources` 的 source 名称可用于 `device`。系统使用 PipeWire 时通过 PulseAudio 兼容服务采集。
- `backend` 可选 `streaming`（默认，边说边显示并自动提交）或 `offline`（SenseVoice，结束录音后 Enter 提交）。
- `punctuation` 默认为 `true`，仅用于流式模式。设为 `false` 可关闭标点模型，空格规范化仍启用；离线 SenseVoice 保持原行为。
- `punctuation_model_dir` 指定标点模型目录，默认 `~/.local/share/fcitx5-voice/punct-ct-transformer-zh-en-int8`，遵守 `XDG_DATA_HOME`。
- `streaming_model_dir` 指定流式模型目录，默认 `~/.local/share/fcitx5-voice/streaming-zipformer-bilingual-zh-en-2023-02-20`。`model_dir` 仅用于离线模式，默认 `~/.local/share/fcitx5-voice/sensevoice`。两个目录均遵守 `XDG_DATA_HOME`。
- 流式模型自动识别中文和英文混输，要求 `language = "auto"`，不能强制单一语言。离线 SenseVoice 支持 `auto/zh/en/ja/ko/yue`。
- `doctor` 只检查依赖、模型存在性和配置，不采集麦克风，不代表桌面兼容性测试通过。
- `systemctl --user status fcitx5-voice` 查看服务；`journalctl --user -u fcitx5-voice -n 30` 查看启动错误。
- 插件报服务不可用时，先确认模型下载完成、服务已就绪；模型加载期间稍后再按快捷键。

## 从离线版升级

重新编译插件并运行安装脚本，下载新的流式模型后重启服务和 Fcitx5。安装脚本保留个人配置；旧配置没有 `backend` 时默认使用流式模式，原有 SenseVoice 文件不会被删除。若旧配置指定了非 `auto` 语言，请先选择离线模式，或将流式模式的语言改为 `auto`。

```bash
python3 scripts/download-model.py --backend streaming
python3 scripts/install-user.py
systemctl --user daemon-reload
systemctl --user restart fcitx5-voice
```

然后从托盘菜单重启 Fcitx5。服务与插件要一起更新：旧插件不支持流式协议。需要保留原来的手动预览体验时，在配置中设置 `backend = "offline"`，并执行 `python3 scripts/download-model.py --backend offline`。

从 0.2.0 流式版升级时，默认下载命令会同时检查语音和标点模型。只补下标点模型可运行 `python3 scripts/download-model.py --punctuation-only`。明确关闭标点时可用 `--no-punctuation` 跳过标点模型下载；同时须在服务配置中设置 `punctuation = false`。

## 验证

```bash
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -e .
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
ctest --test-dir build --output-on-failure
.venv/bin/fcitx5-voice transcribe /path/to/16k-mono-pcm16.wav --repeat 3
```

Python 测试使用合成音频和内存捕获器，不访问真实麦克风。C++ 测试覆盖协议、状态、UTF-8 编辑以及隔离的 Fcitx5 输入上下文。详见 [验证记录](docs/validation.md)。

识别质量尚未以用户真实口述数据集验收。流式模式使用模型端点检测分句，不包含降噪、个人热词、云端后端或自动润色，也不会用离线模型改写已经提交的正文。单次录音仍限制为 30 秒。

## 卸载

```bash
systemctl --user disable --now fcitx5-voice
python3 scripts/install-user.py --uninstall
systemctl --user daemon-reload
```

然后重启 Fcitx5。个人配置和下载模型保留；默认由安装脚本创建的运行环境删除，显式传入 `--runtime-python` 的环境保留。若安装过 `.deb`，还需 `sudo apt remove fcitx5-voice`。卸载 `.deb` 前先运行上述用户级卸载命令（打包副本路径为 `/usr/share/fcitx5-voice/scripts/install-user.py`）。

## 许可证与致谢

LiltKey 的原创代码采用 [MIT 许可证](LICENSE)，Copyright (c) 2026 tangzk and LiltKey contributors。使用、修改和分发时，请保留相应版权与许可声明。

第三方代码、系统组件和预训练模型保留各自的许可证，不因本项目采用 MIT 而改变。具体来源、集成方式和版权原文见 [第三方软件声明](THIRD_PARTY_NOTICES.md) 与 [模型许可说明](MODEL_LICENSES.md)。两份说明和随附许可会包含在 Python 分发包、原生安装和 `.deb` 中；用户级安装后位于 `~/.local/lib/fcitx5-voice/service/`，系统安装文档位于 `/usr/share/doc/fcitx5-voice/`。

感谢以下项目提供的输入法框架、推理工具、音频处理和模型资源：

- [Fcitx5](https://github.com/fcitx/fcitx5)
- [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx)
- [json-c](https://github.com/json-c/json-c)
- [NumPy](https://numpy.org/)
- [GStreamer](https://gstreamer.freedesktop.org/)
- [流式 Zipformer 中英模型](https://huggingface.co/csukuangfj/sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20)
- [CT-Transformer 中英标点模型](https://k2-fsa.github.io/sherpa/onnx/punctuation/pretrained_models.html)
- [SenseVoice 模型](https://huggingface.co/csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17)

模型转换和上游训练项目的来源也列于模型许可说明中；其中 SenseVoice 的模型条款应单独查阅，不能以本项目的 MIT 许可代替。
