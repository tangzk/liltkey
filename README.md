# LiltKey

**以声为键，开口成文。**

[项目宣传页](https://tangzk.github.io/liltkey/) · [许可证](LICENSE)


在光标处边说边输入，支持中英混输和自动标点。识别在本机完成，不上传录音，保留现有拼音输入。

## 安装

适用于 Ubuntu 26.04（amd64）。下载 [deb 安装包](https://github.com/tangzk/liltkey/releases/download/v0.3.0-2/fcitx5-voice_0.3.0-2_amd64.deb)后，用软件中心安装，或运行：

```bash
sudo apt install ./fcitx5-voice_0.3.0-2_amd64.deb
```

安装后自动完成默认配置，无须其他命令。首次请保持联网，等待约 260 MiB 模型下载完成并收到“语音输入已就绪”通知，然后注销并重新登录。

安装会将默认输入法配置为 Fcitx5 并重启输入法，保留已有拼音和语音配置。请先完成正在输入的内容。版本说明与校验文件见 [GitHub Releases](https://github.com/tangzk/liltkey/releases/tag/v0.3.0-2)。

## 开始使用

在使用 Fcitx5 的文本输入框中：

| 操作 | 快捷键 |
|---|---|
| 开始／结束录音 | `Ctrl+Alt+V` |
| 取消当前未提交文字 | `Esc` |

默认使用系统麦克风，停顿后自动加标点并提交文字，每次最多录音 30 秒。再次按快捷键结束录音，已提交的文字会保留。

## 更多文档

- [高级使用与维护](docs/advanced-usage.md)：配置麦克风、识别模式、故障排查、升级与卸载。
- [开发指南](docs/development.md)：源码安装、构建 deb、测试与上游项目。
- [验证记录](docs/validation.md)：测试结果与已知限制。

原创代码采用 [MIT](LICENSE)；第三方软件和模型保留各自许可，详见[第三方声明](THIRD_PARTY_NOTICES.md)及[模型说明](MODEL_LICENSES.md)。
