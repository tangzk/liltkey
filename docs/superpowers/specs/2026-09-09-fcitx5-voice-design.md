# Fcitx5 离线语音输入首版

用户已确认 Fcitx5 原生插件 + 独立语音识别服务。目标系统为 Ubuntu 26.04 GNOME Wayland，Fcitx5 5.1.19，i7-14700K，64 GB 内存。首版完全本地，中文为主；不上传语音，不保存录音或识别文本日志。

## 使用流程

保留现有拼音。插件是全局 Module，监听具有输入上下文的按键。默认 Control+Alt+v 开始录音，再按结束；Esc 取消。结果展示在 Fcitx5 候选面板，Enter 提交，Esc 放弃。预览时 BackSpace 按 Unicode 字符删除末字。仅提交到启动录音时的同一输入上下文；失焦或销毁立即取消，绝不跨窗口自动提交。已有拼音预编辑时不启动。密码/敏感输入上下文禁用。

第一版采用按键结束的短句识别，最多录音 30 秒，达到上限自动结束。无原生流式、无自动润色、无云端。内存音频缓冲，16 kHz、单声道、S16LE。GStreamer pulsesrc 通过 PulseAudio/PipeWire 兼容层采集。模型常驻 CPU，默认 4 线程。模型为 sherpa-onnx 官方 SenseVoice int8 导出，模型需单独下载。

## 模块边界

- `plugin/`：C++20 Fcitx5 Module，json-c 解码协议，非阻塞 Unix Socket 与事件循环，不执行推理或录音。
- `src/fcitx5_voice/`：Python 3.11+ 服务、配置、GStreamer 子进程采集、sherpa-onnx 识别、CLI。
- `tests/`：Python 状态机和真实 socket 协议测试；C++ 插件会话/协议与 Fcitx5 headless 集成测试。
- `scripts/`：模型下载、用户安装和离线构建支持。
- `packaging/`：systemd 用户服务与 Debian 打包。

## 协议 v1

路径 `$XDG_RUNTIME_DIR/fcitx5-voice/service.sock`，目录权限 0700、socket 0600。UTF-8 JSONL，每行最多 65536 字节。仅同 UID 可连接。一个客户端独占麦克风，会话由客户端生成的非空 `id` 标识，最多 128 字节。

服务连接欢迎：`{"type":"ready","protocol":1}`。客户端：`{"type":"start","id":"1"}`、`{"type":"stop","id":"1"}`、`{"type":"cancel","id":"1"}`。服务事件同样携带 id：recording、transcribing、result（text 字段）、cancelled、error（message 字段）。错误有 id 时必须原样回传。busy 表示另一客户端已占用，插件显示错误并断开。拒绝非法类型、过长消息、错误会话 id；不得让它们停止当前合法录音。

结果最多 8192 UTF-8 字节。每段仅一个终态事件。取消和断线立即关闭麦克风，正在执行的模型任务可以完成，但结果作废；旧任务完成不得污染新会话。服务器串行调度推理，有界队列。插件忽略过期 id 的事件，不在键盘回调内阻塞 connect/read/write。

## 验证及交付

先写状态机/协议失效测试，再实现。构建插件，独立 DBus 会话运行 headless Fcitx5 验证按键和文本提交，不操作用户应用。用公开中文样本验证真实模型转写并记录本机推理时间；麦克风仅做设备枚举，不在未由用户触发时录音。交付源码、可构建 `.deb`、用户级安装/卸载、中文 README。任何未实测的桌面行为或识别质量必须明确说明。
