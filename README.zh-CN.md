# LiltKey

**以声为键，开口成文。**

[English](README.md) · 简体中文

[项目宣传页](https://tangzk.github.io/liltkey/zh/) · [许可证](LICENSE)

按住 `Ctrl+Alt` 说话，松开结束，在光标处边说边输入。支持中英混输和自动标点。识别在本机完成，不上传录音，保留现有拼音输入。

![LiltKey 清透浅色主题：Fcitx5 拼音候选框](docs/assets/fcitx5-light-theme.png)

*Fcitx5 真实候选框截图，使用 X11 测试文本框；语音状态沿用同一主题。*

## v0.5.0 新功能

- 可选 SenseVoice 定稿校正：保留边说边出的流式草稿，在停顿或松键提交前，重新识别该段音频。
- 校正失败自动回退到流式识别；取消后不提交迟到结果，全部识别仍在本机完成。
- 校正功能**默认关闭**，需额外准备模型，保留原有快捷键与配置。参见[开启方法](docs/advanced-usage.md#流式预览与快速定稿校正)。
- 宣传页新增[模型对比简报](https://tangzk.github.io/liltkey/zh/research/)，说明本次 CPU 测试与方案选择。

## 安装

适用于 Ubuntu 26.04（amd64）。下载 [deb 安装包](https://github.com/tangzk/liltkey/releases/download/v0.5.0/fcitx5-voice_0.5.0_amd64.deb)后，用软件中心安装，或运行：

```bash
sudo apt install ./fcitx5-voice_0.5.0_amd64.deb
```

安装包已包含清透浅色主题，首次配置默认启用；已有自定义主题、深色偏好和字体会保留。安装后自动完成默认配置，无须其他命令。首次请保持联网，等待约 260 MiB 模型下载完成并收到“语音输入已就绪”通知，然后注销并重新登录。

安装会将默认输入法配置为 Fcitx5 并重启输入法，保留已有拼音和语音配置。请先完成正在输入的内容。版本说明与校验文件见 [GitHub Releases](https://github.com/tangzk/liltkey/releases/tag/v0.5.0)。

## 开始使用

在使用 Fcitx5 的文本输入框中：

| 操作 | 快捷键 |
|---|---|
| 按住录音，松开结束 | 长按 `Ctrl+Alt`（约 300 毫秒） |
| 切换开始／结束录音 | `Ctrl+Alt+V` |
| 取消当前未提交文字 | `Esc` |

默认使用系统麦克风，停顿后自动加标点并提交文字。按住 `Ctrl+Alt` 可持续录音，松开任意一个键后结束并处理尾句；短按或紧接其他按键不会启动录音。`Ctrl+Alt+V` 仍可切换录音，使用该方式时每次最多 30 秒。已提交的文字会保留。

## 更多文档

- [高级使用与维护](docs/advanced-usage.md)：配置麦克风、识别模式、故障排查、升级与卸载。
- [开发指南](docs/development.md)：源码安装、构建 deb、测试与上游项目。
- [主题与恢复](themes/README.md)：默认主题、切换外观与恢复原设置。
- [验证记录](docs/validation.md)：测试结果与已知限制。

原创代码采用 [MIT](LICENSE)；第三方软件和模型保留各自许可，详见[第三方声明](THIRD_PARTY_NOTICES.md)及[模型说明](MODEL_LICENSES.md)。
