# 光标处流式语音输入

用户已批准实现会话内讨论的方案：本地流式 ASR → Fcitx5 client preedit → 分句正式提交。保留当前离线 SenseVoice 预览模式作为显式兼容选项。

- 默认 streaming backend，使用 sherpa-onnx 1.13.7 的中英双语流式 transducer；模型与下载文件固定 revision 和 SHA256。
- PCM16/16 kHz/mono 持续送入有界队列；只有独立工作线程执行推理，主事件循环不阻塞。队列溢出明确报错，禁止无声丢音频。
- 在线识别器每会话创建 decoder，`accept(pcm)`、`finish()` 返回 `(kind, text)` 列表；kind 是 partial 或 final，text 是当前句完整文本。finish 必须排空尾音，不重复提交已定稿句子。
- socket 流式模式 protocol=2，离线仍 protocol=1。服务发送 recording、partial、final、transcribing、finished、cancelled、error。partial/final 带 id、segment（从 1 开始）、seq（会话内单调增长）。空 final 合法，用于清空被修正为空的预编辑并结束当前 segment。
- 插件仅接受当前会话、当前 segment、更新的 seq；final 只提交一次。finished 结束整个会话。每次显示与提交都检查仍绑定原输入上下文且有焦点。
- 临时文字用 client preedit，客户端无 Preedit 能力则用输入法面板 preedit。支持下划线与 Unicode 光标位置。句子定稿清空预编辑后 commitString。
- 快捷键开始/停止；Esc 放弃未提交部分；普通键盘输入、失焦、reset、销毁、切换输入法或进入敏感框均取消。已提交文字不回退。鼠标事件只能依据客户端提供的 reset/焦点等信号处理，不承诺任意应用的光标锁定。
- 停止时先停止采集并排空音频，再 finish；取消时先失效会话并停止采集，工作线程结果不可再提交。已有离线测试继续通过。
- 默认单会话上限保持 30 秒，可多次分句；本次不引入 LLM 润色或二次 SenseVoice 定稿。
- 同一会话连续英文分句之间保留词边界：上一句以 ASCII 字母数字或英文标点结尾、下一句以 ASCII 字母数字开头时，预编辑与提交都补一个空格；中文分句直接相邻。
- 不保存录音/转写日志，不自动触发麦克风测试。真实模型验证使用显式公开 WAV；桌面手工验收范围如实报告。
