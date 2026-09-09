# Fcitx5 本地语音输入

Fcitx5 原生模块 + 独立 SenseVoice 识别服务。保留现有拼音输入，语音识别在本机 CPU 执行。首版支持中文及模型原生支持的中英等语言；不上传录音、不保存语音或识别文本日志。

## 使用

在支持 Fcitx5 的文本输入框内：

| 操作 | 按键 |
|---|---|
| 开始录音／结束录音 | `Ctrl+Alt+V` |
| 提交预览文字 | `Enter` |
| 删除预览末尾一个字符 | `Backspace` |
| 取消录音／放弃预览 | `Esc` |

录音最多 30 秒。改用普通键盘输入、切换窗口或输入框会取消本次会话，不会把结果写入另一个窗口。已有拼音预编辑时先完成或取消拼音；密码和标记为敏感的输入框禁用语音。快捷键通过 Fcitx5 附加组件配置修改。

首版是按键结束的短句识别，不是边说边逐字显示。预览支持末尾删除；其他修改可在提交后使用应用的编辑功能。输入框必须正常接入 Fcitx5；这不是绕过 Wayland 限制的任意全局按键注入工具。

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

用户级安装不会更换默认输入法或改写现有拼音配置。模型固定到上游 revision，并验证 SHA256，下载失败不会替换已可用模型。默认量化模型约 239 MB，另外需要 Python 运行依赖。

## Debian 安装包

构建后执行：

```bash
python3 scripts/build-deb.py
sudo apt install ./dist/fcitx5-voice_0.1.0_amd64.deb
fcitx5-voice-setup
fcitx5-voice-download-model
systemctl --user daemon-reload
systemctl --user enable --now fcitx5-voice
```

`.deb` 包含原生插件和服务源码，**不包含模型和 Python 第三方依赖**；两个 setup/download 命令安装它们。不要用 sudo 运行这些用户级命令。最后重启 Fcitx5。

## 配置与诊断

服务配置：`~/.config/fcitx5-voice/config.toml`，遵守 `XDG_CONFIG_HOME`。参见 [config.example.toml](config.example.toml)。修改后执行 `systemctl --user restart fcitx5-voice`。

```toml
threads = 4
max_seconds = 30
language = "auto"
device = ""
```

- `device` 为空时使用系统默认麦克风。运行 `fcitx5-voice devices` 查询音频设备；`pactl list short sources` 的 source 名称可用于 `device`。系统使用 PipeWire 时通过 PulseAudio 兼容服务采集。
- `model_dir` 可指定模型绝对路径；默认 `~/.local/share/fcitx5-voice/sensevoice`，遵守 `XDG_DATA_HOME`。
- `language` 可选 `auto/zh/en/ja/ko/yue`；中英混输建议 `auto`。
- `doctor` 只检查依赖、模型存在性和配置，不采集麦克风，不代表桌面兼容性测试通过。
- `systemctl --user status fcitx5-voice` 查看服务；`journalctl --user -u fcitx5-voice -n 30` 查看启动错误。
- 插件报服务不可用时，先确认模型下载完成、服务已就绪；模型加载期间稍后再按快捷键。

## 验证

```bash
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -e .
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
ctest --test-dir build --output-on-failure
.venv/bin/fcitx5-voice --model-dir models/sensevoice transcribe /path/to/16k-mono-pcm16.wav --repeat 3
```

Python 测试使用合成音频和内存捕获器，不访问真实麦克风。C++ 测试覆盖协议、状态、UTF-8 编辑以及隔离的 Fcitx5 输入上下文。详见 [验证记录](docs/validation.md)。

识别质量尚未以用户真实口述数据集验收；速度快不等于准确率达标。首版未实现神经网络 VAD、降噪、个人热词、连续听写、云端后端或自动润色。服务已有模型适配边界，可以在同一组录音上比较候选模型再替换。

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
- [SenseVoice 模型](https://huggingface.co/csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17)

预训练模型使用其自身许可证，和本项目源码分开管理。
