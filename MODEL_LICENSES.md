# 模型来源与许可

核对日期：2026-09-11。

LiltKey 原创代码使用根目录 [MIT 许可证](LICENSE)。模型权重、词表及其转换版本由各自权利人授权，**不因 LiltKey、推理库或训练代码的许可而改用 MIT**。下文记录本项目所引用的具体模型及上游声明，不替上游补授许可。

当前模型权重不随 Git 仓库或 `.deb` 分发，由下载脚本单独获取。下载地址、固定 revision、所需文件和 SHA-256 的唯一执行依据是 [model_manifest.py](src/fcitx5_voice/model_manifest.py)。哈希用于核验文件完整性，不能代替模型许可。

| 模型 | 在 LiltKey 中的用途 | 已核对的权重许可声明 |
| --- | --- | --- |
| Streaming Zipformer 中英双语 | 流式语音识别 | 固定版本模型卡标注 Apache-2.0；该版本未提供独立 LICENSE 文件 |
| SenseVoiceSmall，sherpa-onnx 转换版 | 离线语音识别及可选流式定稿校正 | 固定版本 LICENSE 指向 FunASR 许可说明；官方原始模型卡指向 FunASR 模型协议 v1.1，属于自定义模型许可 |
| CT-Transformer，sherpa-onnx INT8 转换版 | 为识别文本恢复标点 | 原始 ModelScope 模型卡标注 Apache License 2.0；转换时的原始权重 commit 尚未固定或确认 |

## Streaming Zipformer

- 转换发布者：csukuangfj / sherpa-onnx。
- 下载仓库：[`csukuangfj/sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20`](https://huggingface.co/csukuangfj/sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20/tree/98590b7ed6443e77b714204da2757d75e1a642f4)。
- 固定 revision：`98590b7ed6443e77b714204da2757d75e1a642f4`。
- 使用文件：`encoder-epoch-99-avg-1.int8.onnx`、`decoder-epoch-99-avg-1.onnx`、`joiner-epoch-99-avg-1.int8.onnx`、`tokens.txt`。

该 revision 的 [README 模型卡](https://huggingface.co/csukuangfj/sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20/blob/98590b7ed6443e77b714204da2757d75e1a642f4/README.md) 明确标注 `license: apache-2.0`，并将原始 TorchScript 模型归属到 [`pfluo/k2fsa-zipformer-chinese-english-mixed`](https://huggingface.co/pfluo/k2fsa-zipformer-chinese-english-mixed)。原始模型卡也标注 Apache-2.0。其训练代码来自 [icefall](https://github.com/k2-fsa/icefall/tree/master/egs/librispeech/ASR/pruned_transducer_stateless7_streaming)，此处仅用于说明来源。

许可依据是模型卡中的声明；[Apache License 2.0 正文](https://www.apache.org/licenses/LICENSE-2.0.txt) 规定了再分发时提供许可证、保留适用声明、注明修改及处理上游 NOTICE 等条件。所核对的固定模型仓库中没有单独的 LICENSE 或 NOTICE。原始训练权重的精确 commit 未由该模型卡固定；[sherpa 官方说明](https://k2-fsa.github.io/sherpa/onnx/pretrained_models/online-transducer/zipformer-transducer-models.html#csukuangfj-sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20-bilingual-chinese-english) 将训练数据描述为社区贡献模型使用的内部数据，本项目未核验完整训练数据的权利来源。

## SenseVoiceSmall

- 原始模型：**SenseVoiceSmall by FunASR / FunAudioLLM**（Alibaba Group）；[官方模型卡](https://huggingface.co/FunAudioLLM/SenseVoiceSmall)、[官方源码项目](https://github.com/FunAudioLLM/SenseVoice)（现重定向至 QwenAudio/SenseVoice）。
- 转换发布者及下载仓库：[`csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17`](https://huggingface.co/csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/tree/2365baeacb507f821a0c8120fcee3d484dba7a07)。
- 固定 revision：`2365baeacb507f821a0c8120fcee3d484dba7a07`。
- 使用文件：`model.int8.onnx`、`tokens.txt`。

转换仓库该版本的 [LICENSE](https://huggingface.co/csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/blob/2365baeacb507f821a0c8120fcee3d484dba7a07/LICENSE) 只有指向 [FunASR 许可说明](https://github.com/modelscope/FunASR#license) 的引用，并非 MIT 许可正文。官方原始模型卡标注 `license: other`，链接 [FunASR Model Open Source License Agreement](https://github.com/modelscope/FunASR/blob/main/MODEL_LICENSE)。FunASR 和 SenseVoice 的源码 MIT 许可与模型权重许可分开。

已保存协议 v1.1 的[未改动原文](licenses/models/FunASR-MODEL_LICENSE-v1.1.txt)，来源为 FunASR commit [`486b4b7ceb27b72db24a84c6e1be7cf6c5be6609`](https://github.com/modelscope/FunASR/blob/486b4b7ceb27b72db24a84c6e1be7cf6c5be6609/MODEL_LICENSE)，文件 SHA-256 为 `7dba975a2069691db4992b0592d70828b330d2f8a30a71450f4e152a554e84f8`。这是本次查阅快照；该 commit 不是模型下载 revision。

协议涉及权重和微调衍生物，要求注明出处和作者并保留模型名称，另有行为限制、许可终止和自动修订条款。原文中的占位符也按上游保留。本项目不将此自定义许可标为 MIT、Apache-2.0 或经 OSI 认可的开源许可证；“模型开源协议”是其上游名称。

商用解释仍需区分不同来源的状态：[官方 README 许可节](https://github.com/QwenAudio/SenseVoice/blob/ea15219509625e5d4c5143c37c86970135886b5d/README.md#license) 和 [2026-07-26 的成员答复](https://github.com/QwenAudio/SenseVoice/issues/334#issuecomment-5083546605) 说明，遵守协议时可商用官方权重，且第 3 节属于责任免责声明。但该 issue 的 [2026-08-29 后续答复](https://github.com/QwenAudio/SenseVoice/issues/334#issuecomment-5463240506) 已重新打开问题，将此前解释降为背景说明，等待许可权利人或核心维护者确认。因此，本说明不作“权利人已最终确认可无条件商用”的承诺，也不擅自把协议改写为“仅限非商业使用”。

转换脚本引用 `iic/SenseVoiceSmall`，但未固定原始权重 revision；转换仓库 LICENSE 的外链也未固定 FunASR 协议版本。本文记录已核对的声明链和当前协议快照，不能由此证明历史版本的完整授权链；上述官方权重解释本身也提示须另查第三方转换制品的声明。

## CT-Transformer 标点模型

- 原始模型及作者：Alibaba 达摩院语音团队 / iic，[`punc_ct-transformer_zh-cn-common-vocab272727-pytorch`](https://modelscope.cn/models/iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch/summary)。
- 转换发布者：csukuangfj / k2-fsa/sherpa-onnx；[官方转换说明](https://k2-fsa.github.io/sherpa/onnx/punctuation/pretrained_models.html)。
- 下载位置：GitHub release 标签 [`punctuation-models`](https://github.com/k2-fsa/sherpa-onnx/releases/tag/punctuation-models)。此标签不是不可变的模型 commit。
- 固定归档：[`sherpa-onnx-punct-ct-transformer-zh-en-vocab272727-2024-04-12-int8.tar.bz2`](https://github.com/k2-fsa/sherpa-onnx/releases/download/punctuation-models/sherpa-onnx-punct-ct-transformer-zh-en-vocab272727-2024-04-12-int8.tar.bz2)。
- 归档 SHA-256：`c0d5aa5f8eeb686032345e180bedf39319dc2e0556781c6264bcadba8328a6e1`；与核对时 GitHub 官方 release asset 的 digest 一致。
- 使用归档成员：`sherpa-onnx-punct-ct-transformer-zh-en-vocab272727-2024-04-12-int8/model.int8.onnx`。
- 模型 SHA-256：`65a3fb9f5ad7bfb96bf69e0dc4481df97f6ee60513c1d94ce981ba6effd524b1`。

原始 ModelScope 仓库的当前模型卡及 [`v2.0.4` 模型卡](https://modelscope.cn/api/v1/models/iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch/repo?Revision=v2.0.4&FilePath=README.md) 均标注 `license: Apache License 2.0`。许可记录以这个具体模型的声明为依据，不因它由 FunASR 工具转换便改用 FunASR 自定义模型协议。

同名 sherpa 转换模型的 [README](https://huggingface.co/csukuangfj/sherpa-onnx-punct-ct-transformer-zh-en-vocab272727-2024-04-12/blob/432aeba669265e7aeb06b9359753419683b38597/README.md) 明确指向上述 ModelScope 源，但转换命令没有固定原始权重 commit。`v2.0.4` 是本次核对许可的来源，不能据此声称它就是 INT8 归档的精确输入版本。归档名中的 `2024-04-12` 也不是 INT8 资产上传时间；该资产元数据记录其于 2025-06-18 上传。

本次未下载大模型或检查该 INT8 归档中的许可附件；因此归档内部是否有额外声明尚未核验。未来若将模型权重另行打包、镜像或再分发，应先核对实际制品中的声明及原始版本，并按适用许可保留原作者、模型名称和许可材料。
