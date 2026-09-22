# 流式预览与 SenseVoice 定稿校正：2026-09-22

本文记录 v0.5.0 集成阶段。后续 v0.5.1 已将校正改为默认开启，并由安装器自动准备模型；下文“默认关闭”是该阶段的历史设置。

## 交付

保留现有 Zipformer 中英流式预览，在停顿分句、20 秒音频上限或松键时，用本地 SenseVoice 对尚未提交的音频重识别，再提交最终文字。SenseVoice 使用自身标点。已提交正文不再修改。

增加 `streaming_refine` 配置、模型下载选项、安装器准备和诊断检查。项目默认关闭以兼容旧安装；本机个人配置已开启，Python 服务已更新并重启，启动日志确认服务就绪，已安装命令的 `doctor` 全部通过。快捷键、录音设备和 Fcitx5 插件保持原设置。

校正加载失败时仍提供原流式识别；单次校正失败时保留已有文字及原 decoder 的预读内容，本次录音剩余部分继续使用原流式路径。下一次录音重新尝试校正。取消或失焦后丢弃迟到结果。音频仅在内存暂存，每段上限 640,000 字节。

## 验证

- Python：148 项测试全部通过，包括分段、取消竞态、校正失败后的预读保留、无预览的最终识别、20 秒边界与配置/下载/安装流程。
- C++：在新的临时构建目录重新编译，5 项 CTest 全部通过，覆盖状态、缓冲、插件集成、流式与长按。
- 独立代码复查发现的异常回退丢失预读问题已通过回归测试修复，复查无剩余重要问题。
- 已安装的 `fcitx5-voice transcribe` 使用个人配置成功输出“钙钾等元素属于金属、银和金等元素当然也是金属。”；原流式预览在此处为“盖甲”。

使用产品中的 `build_streaming` 和 `StreamingSession`，以内存捕获器按真实语速每 100 ms 输入公开录音，在最后一块到达后发送 stop：

| 回放 | 音频长度 | stop 到 finished |
| --- | ---: | ---: |
| 中文 zh-0001 | 8.28 秒 | 40 毫秒 |
| 英文 en-0004 | 4.32 秒 | 138 毫秒 |
| 两段中文、一段英文及间隔静音 | 25.98 秒 | 199 毫秒 |

连续回放输出三个非空 final，各段只提交一次；英文短句在没有流式草稿的情况下仍能完整定稿。中文独立回放另有一个空 final，用于清除尾部预编辑，不会重复提交正文。

以上只有三个回放场景，不是延迟分位数或上限保证。不包含真实麦克风、IPC 或桌面输入框延迟，保留了原录音的前后静音；部分校正在 stop 之前已开始。英文临时预览仍受现有 Zipformer 质量限制；20 秒硬分段可能影响边界词。未采集用户实际麦克风录音。

## 复现与恢复

详细回放脚本与事件日志保留在本机评测目录，未随仓库发布。所用模型及样本规则见[模型评测](2026-09-22-asr-model-evaluation.md)。本机更新前已备份个人配置和 Python 服务。

如需恢复原识别体验，将 `~/.config/fcitx5-voice/config.toml` 中的 `streaming_refine` 改为 `false`，然后执行 `systemctl --user restart fcitx5-voice`。无需移除模型。

构建环境原 `.venv/bin/cmake` 启动脚本和旧 build 缓存仍引用迁移前的仓库路径；本次未修改它们，使用实际 CMake 二进制和临时构建目录完成验证：

```bash
PYTHONPATH=src ~/.local/share/fcitx5-voice/venv/bin/python -m unittest discover -s tests
.venv/lib/python3.11/site-packages/cmake/data/bin/cmake -S . -B /tmp/liltkey-refinement-build -DBUILD_TESTING=ON
.venv/lib/python3.11/site-packages/cmake/data/bin/cmake --build /tmp/liltkey-refinement-build -j4
.venv/lib/python3.11/site-packages/cmake/data/bin/ctest --test-dir /tmp/liltkey-refinement-build --output-on-failure
```
