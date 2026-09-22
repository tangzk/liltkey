# 高级使用与维护

[返回快速开始](../README.md) · [开发指南](development.md)

## 使用

在支持 Fcitx5 的文本输入框内：

| 操作 | 按键 |
|---|---|
| 持续录音／结束录音 | 按住 `Ctrl+Alt` 约 300 毫秒／松开任意一个键 |
| 切换开始／结束录音 | `Ctrl+Alt+V` |
| 放弃当前未提交文字并停止 | `Esc` |
| 离线模式提交／删除预览末字 | `Enter` / `Backspace` |

长按 `Ctrl+Alt` 时持续录音，不受 `max_seconds` 限制；左右 Ctrl、Alt 均可使用（AltGr 不属于 Alt），先按哪一个都可以。短按、在等待期间按其他键、切换焦点或重置输入状态都会取消待触发的录音。`Ctrl+Alt+V` 切换模式仍按 `max_seconds` 自动结束（默认 30 秒）。期间可提交多句话。正在识别的文字属于预编辑，可能随上下文修正；停顿后正式提交，录音继续。松开长按组合键或再次按切换快捷键会结束录音、处理剩余音频并提交尾句，无须按 Enter。Esc 只放弃当前未提交部分，已提交句子保留。

流式模式默认在定稿前使用本地中英标点模型恢复逗号、句号、问号，并整理空格。临时文字持续显示，标点在分句定稿时出现；中文词间不加空格，中英相邻按“使用 Linux 系统”处理，英文保留词间空格。模型根据当前分句文字预测标点，可能判断不准；不会回改已提交正文。标点推理异常时保留原始文字并继续听写。

改用普通键盘输入、切换窗口或输入框、客户端重置输入状态时会取消本次会话。已有拼音预编辑时先完成或取消拼音；密码和标记为敏感的输入框禁用语音。切换快捷键通过 Fcitx5 附加组件配置修改；长按组合固定为 Ctrl+Alt。

输入框必须正常接入 Fcitx5。支持客户端预编辑的应用在光标处显示下划线文字；不支持时退回输入法面板预编辑。鼠标在同一输入框移动光标时，能否及时取消取决于应用是否发送 reset 等输入法事件，不能保证任意应用的光标锁定。语音模式下 Enter 属于普通键盘输入，不会代替停止快捷键。

## 安装与自动配置

安装完成后会在当前桌面用户会话中自动初始化：创建独立 Python 运行环境，下载并校验中英流式语音和标点模型，写入默认配置，启用识别服务自启动，设置默认输入法为 Fcitx5 并重启输入法。请先结束正在输入的拼音预编辑。

首次初始化需要联网下载依赖和约 260 MiB 模型。收到“语音输入已就绪”的桌面通知后即可长按 `Ctrl+Alt` 录音、松开结束，或使用 `Ctrl+Alt+V` 切换开始／结束，`Esc` 取消；默认开启自动标点，使用系统默认麦克风。首次安装或切换输入法后，请注销并重新登录，让所有应用加载输入法环境。

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
streaming_refine = false
punctuation = true
threads = 4
max_seconds = 30
language = "auto"
device = ""
```

- `max_seconds` 为切换录音模式的时长上限（1–30 秒），不限制长按录音。长时间口述建议使用默认流式模式，音频逐块处理；离线模式在内存中保留整段音频，松键后按最多 30 秒分段识别并合并预览，分段边界可能影响识别质量。
- `device` 为空时使用系统默认麦克风。运行 `fcitx5-voice devices` 查询音频设备；`pactl list short sources` 的 source 名称可用于 `device`。系统使用 PipeWire 时通过 PulseAudio 兼容服务采集。
- `backend` 可选 `streaming`（默认，边说边显示并自动提交）或 `offline`（SenseVoice，结束录音后 Enter 提交）。
- `streaming_refine` 默认为 `false`。设为 `true` 时保留流式草稿，在每段提交前用 SenseVoice 重识别该段音频；失败时保留原流式结果。参见下方开启步骤。
- `punctuation` 默认为 `true`，仅用于流式模式。设为 `false` 可关闭标点模型，空格规范化仍启用；SenseVoice（离线或定稿校正）自带标点，不再重复使用该标点模型。
- `punctuation_model_dir` 指定标点模型目录，默认 `~/.local/share/fcitx5-voice/punct-ct-transformer-zh-en-int8`，遵守 `XDG_DATA_HOME`。
- `streaming_model_dir` 指定流式模型目录，默认 `~/.local/share/fcitx5-voice/streaming-zipformer-bilingual-zh-en-2023-02-20`。`model_dir` 用于离线模式和流式定稿校正，默认 `~/.local/share/fcitx5-voice/sensevoice`。两个目录均遵守 `XDG_DATA_HOME`。
- 流式模型自动识别中文和英文混输，要求 `language = "auto"`，不能强制单一语言。离线 SenseVoice 支持 `auto/zh/en/ja/ko/yue`。
- `doctor` 只检查依赖、模型存在性和配置，不采集麦克风，不代表桌面兼容性测试通过。
- `systemctl --user status fcitx5-voice` 查看服务；`journalctl --user -u fcitx5-voice -n 30` 查看启动错误。
- 插件报服务不可用时，先确认模型下载完成、服务已就绪；模型加载期间稍后再按快捷键。

## 流式预览与快速定稿校正

在项目根目录先下载并校验 SenseVoice（已有模型会跳过下载）：

```bash
python3 scripts/download-model.py --with-refinement
```

deb 安装用户无须检出源码，可改用以下命令准备模型（已有模型会校验后跳过）：

```bash
fcitx5-voice-download-model --with-refinement
```

然后在个人 `config.toml` 中设置：

```toml
backend = "streaming"
streaming_refine = true
```

执行 `fcitx5-voice doctor`，确认 SenseVoice 校正模型就绪，再执行 `systemctl --user restart fcitx5-voice`。使用自定义 `model_dir` 时，改用 `python3 scripts/download-model.py --backend offline --dest /你的模型目录`；一键安装器也会按配置准备这个目录。

录音时继续显示流式草稿；停顿分句或松键时，SenseVoice 用该段原始音频生成最终文字，再提交一次。它不会修改已经提交到应用的正文。SenseVoice 自带标点，不重复套用 CT-Transformer；校正失败时保留原流式结果和原标点设置，并在本次录音剩余时间继续使用原流式识别，下一次录音再尝试校正。若校正模型无法加载，服务会在日志中提示并继续提供原流式识别，`doctor` 会报告缺失文件。

每段最多保留 20 秒 PCM（约 625 KiB），仅存于内存，不保存录音文件、不上传。持续录音会在停顿或达到此上限时定稿并开始下一段；上限处硬分段可能影响边界词准确率。Esc、失焦或断开后仍丢弃未提交结果。校正增加少量处理时间，具体取决于录音长度和 CPU 负载；它不会改善流式模型本身的临时识别质量。

关闭时将 `streaming_refine` 改回 `false` 并重启服务，即恢复原流式路径；无需卸载模型。此功能默认关闭，避免旧安装升级后新增下载或模型依赖。

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
