# 开发指南

[返回快速开始](../README.md) · [高级使用与维护](advanced-usage.md)

Fcitx5 原生模块与独立本地识别服务组成语音输入功能，默认使用中英双语流式 Zipformer，保留 SenseVoice 离线预览模式，并提供可选的 SenseVoice 流式定稿校正。目标环境为 Ubuntu 26.04、Fcitx5 5.1.19 或更新版本。

以下命令均在项目根目录执行。

## 源码安装（开发者）

在项目目录中，以当前桌面用户执行：

```bash
bash install.sh
```

它会自动安装系统开发依赖、编译插件并完成配置。只有系统包安装使用 sudo，其余步骤使用当前用户。重复运行可升级。开发构建缓存与一键安装的 `build/installer` 分开。

构建 deb：

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j4
python3 scripts/build-deb.py
```

安装包输出至 `dist/`，不包含模型或第三方 Python 依赖，用户桌面中的自动初始化会负责下载。底层 `scripts/install-user.py`、`scripts/download-model.py` 和 `fcitx5-voice-setup` 仍供开发调试或故障排查使用，正常安装无需手动运行它们。

## 验证

```bash
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -e .
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
ctest --test-dir build --output-on-failure
.venv/bin/fcitx5-voice transcribe /path/to/16k-mono-pcm16.wav --repeat 3
```

Python 测试使用合成音频和内存捕获器，不访问真实麦克风。C++ 测试覆盖协议、状态、UTF-8 编辑以及隔离的 Fcitx5 输入上下文。详见 [验证记录](validation.md)。

识别质量尚未以用户真实口述数据集验收。流式模式使用模型端点检测分句，不包含降噪、个人热词、云端后端或自动润色，也不会用离线模型改写已经提交的正文。长按 Ctrl+Alt 录音持续到松键，Ctrl+Alt+V 切换模式仍有默认 30 秒上限。

## 卸载源码安装

```bash
systemctl --user disable --now fcitx5-voice
python3 scripts/install-user.py --uninstall
systemctl --user daemon-reload
```

然后重启 Fcitx5。个人配置和下载模型保留；默认由安装脚本创建的运行环境删除，显式传入 `--runtime-python` 的环境保留。

## 上游

- [Fcitx5](https://github.com/fcitx/fcitx5)
- [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx)
- [流式 Zipformer 中英模型](https://huggingface.co/csukuangfj/sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20)
- [CT-Transformer 中英标点模型](https://k2-fsa.github.io/sherpa/onnx/punctuation/pretrained_models.html)
- [SenseVoice 模型](https://huggingface.co/csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17)

预训练模型使用其自身许可证，和本项目源码分开管理。

## 长按录音协议

协议 1、2 的 `start` 消息均支持可选布尔字段 `continuous`，省略时为 `false`。长按模式发送 `{"type":"start","id":"…","continuous":true}`，服务同时禁用自动停止计时和 PCM 总量截断。松键发送原有 `stop` 消息；连接或录音启动尚未完成时取消会话。客户端断开、失焦和取消仍会释放麦克风。插件和服务需一起升级才能使用持续录音。

## 流式定稿校正

`streaming_refine` 默认 `true`，开启时，`RefinedStreamingRecognizer` 包装原流式识别器；协议仍为版本 2，插件无需更改。每段 PCM 在端点、20 秒上限或松键时送入 SenseVoice。已提交音频块的预读状态随旧流式 decoder 一起丢弃，下一段从新的 native stream 开始，避免同一音频被重复定稿。单段缓冲上限为 640,000 字节；捕获队列仍有原来的两秒容量限制。

成功校正只做文本/空格规范化，使用 SenseVoice 自带标点；无效结果或推理异常回退至流式结果。`StreamingSession` 在工作线程返回后再次校验会话状态，所以取消或失焦后的校正不能产生迟到提交。测试覆盖音频分段边界、无预览定稿、持续录音上限、取消、加载失败和下载配置。校正只在原协议的 final 提交前发生。
