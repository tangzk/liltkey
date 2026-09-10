# Fcitx5 本地语音输入

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

## 从源码安装（推荐）

目标：Ubuntu 26.04、Fcitx5 5.1.19。其他版本需要在对应系统上重新编译并验证。

安装系统开发依赖：

```bash
sudo apt install build-essential cmake pkg-config libfcitx5core-dev libfcitx5config-dev libfcitx5utils-dev libjson-c-dev python3-venv gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good
```

构建插件：

```bash
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

## Debian 安装包

构建后执行：

```bash
python3 scripts/build-deb.py
sudo apt install ./dist/fcitx5-voice_0.3.0_amd64.deb
fcitx5-voice-setup
fcitx5-voice-download-model
systemctl --user daemon-reload
systemctl --user enable --now fcitx5-voice
```

`.deb` 包含原生插件和服务源码，**不包含模型和 Python 第三方依赖**；两个 setup/download 命令安装它们。不要用 sudo 运行这些用户级命令。最后重启 Fcitx5。

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

## 上游

- [Fcitx5](https://github.com/fcitx/fcitx5)
- [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx)
- [流式 Zipformer 中英模型](https://huggingface.co/csukuangfj/sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20)
- [CT-Transformer 中英标点模型](https://k2-fsa.github.io/sherpa/onnx/punctuation/pretrained_models.html)
- [SenseVoice 模型](https://huggingface.co/csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17)

预训练模型使用其自身许可证，和本项目源码分开管理。
