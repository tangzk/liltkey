# 高级使用与维护

[返回快速开始](../README.md) · [开发指南](development.md)

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

## 安装与自动配置

安装完成后会在当前桌面用户会话中自动初始化：创建独立 Python 运行环境，下载并校验中英流式语音和标点模型，写入默认配置，启用识别服务自启动，设置默认输入法为 Fcitx5 并重启输入法。请先结束正在输入的拼音预编辑。

首次初始化需要联网下载依赖和约 260 MiB 模型。收到“语音输入已就绪”的桌面通知后即可使用 `Ctrl+Alt+V` 开始／结束，`Esc` 取消；默认开启自动标点，使用系统默认麦克风。首次安装或切换输入法后，请注销并重新登录，让所有应用加载输入法环境。

如果安装时没有图形桌面会话，首次登录桌面时会自动初始化。下载失败会每 5 分钟重试；关机或注销后，下次登录继续。安装包已装好与模型已就绪是两个阶段，模型尚未下载完成时不能识别。初始化成功后，后续登录不再重复安装。识别过程不需要联网。

升级或重新安装 deb 会重新检查配置和模型，并保留个人语音配置及拼音设置。如果原有配置选择离线模式、自定义模型目录或关闭标点，会按该配置准备模型。手动管理的 `~/.xinputrc` 不会被覆盖；若它阻止 `im-config` 切换输入法，日志会提示原因。

需要排查后台配置状态时：

```bash
journalctl --user -u fcitx5-voice-setup -n 50
```

状态文件为 `~/.local/share/fcitx5-voice/setup-status.json`（遵守 `XDG_DATA_HOME`），`status` 为 `installing`、`failed` 或 `ready`。配置完成后的识别日志位于 `fcitx5-voice` 用户服务。

## 默认主题

deb 0.3.0-3 起附带 LiltKey 清透浅色主题。首次配置将原有默认浅色主题切换为新主题，保留自定义主题、深色偏好、非默认字体与已有候选词排列方式。后续升级仅更新主题资源，不再覆盖用户的外观选择。可在“Fcitx 5 配置 → 附加组件 → 经典用户界面”中自行切换，详见[主题与恢复](../themes/README.md)。

## 配置与诊断

服务配置：`~/.config/fcitx5-voice/config.toml`，遵守 `XDG_CONFIG_HOME`。参见 [config.example.toml](../config.example.toml)。修改后执行 `systemctl --user restart fcitx5-voice`。

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

## 升级

deb 用户直接安装新版 deb，自动初始化会更新服务并重启 Fcitx5，保留个人配置。源码安装直接再次运行 `bash install.sh`。

旧配置没有 `backend` 时默认使用流式模式。若旧配置指定了非 `auto` 语言，需要将 `backend` 设为 `"offline"` 保持离线体验，或将 `language` 改为 `"auto"` 使用流式模式。配置不合法时安装器在修改系统前退出并说明原因。

## 卸载

通过 deb 安装时，使用软件中心卸载或运行：

```bash
sudo apt remove fcitx5-voice
```

会停止已登录用户的后台配置任务和识别服务，并移除系统插件及登录自启动入口。个人配置、下载模型、用户主题和用户运行环境保留；包移除后生成的用户服务不会启动。默认输入法设置保留为 Fcitx5，现有拼音输入不变。

源码安装的卸载步骤见[开发指南](development.md#卸载源码安装)。
