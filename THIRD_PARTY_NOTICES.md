# 第三方软件声明

LiltKey 的原创代码采用根目录 [LICENSE](LICENSE) 中的 MIT 许可证。第三方软件和模型保留各自的版权与许可；本文件不改变这些条款。以下清单依据 `CMakeLists.txt`、`pyproject.toml`、实际 API/命令调用和目标 Ubuntu 环境核对，核对日期为 2026-09-11。

## 直接链接或导入的软件

| 组件、版本与上游 | 本项目中的用途和集成方式 | 许可与随附声明 |
| --- | --- | --- |
| [Fcitx5](https://github.com/fcitx/fcitx5/tree/5.1.19)，目标版本 5.1.19 | 原生插件使用 Core、Config、Utils 的开发头文件和 API，动态链接系统提供的 `libFcitx5Core.so.7`、`libFcitx5Config.so.6`、`libFcitx5Utils.so.2`。 | 这些库采用 **LGPL-2.1-or-later**，可核对 [5.1.19 SDK 头文件声明](https://github.com/fcitx/fcitx5/blob/5.1.19/src/lib/fcitx/addoninstance.h) 与[上游许可原文](https://github.com/fcitx/fcitx5/blob/5.1.19/LICENSES/LGPL-2.1-or-later.txt)。随附 [Fcitx5 版权记录](licenses/Fcitx5-COPYRIGHT.txt) 和 [LGPL 2.1 原文](licenses/LGPL-2.1-or-later.txt)。 |
| [json-c](https://github.com/json-c/json-c/tree/json-c-0.18-20240915)，当前 sysroot 为 0.18 | `plugin/session.cpp` 使用 JSON 解析与序列化接口。当前本地 sysroot 构建把 `libjson-c.a` 静态链接进原生插件；使用系统开发包构建时，链接形式取决于其 CMake 导出配置。 | **MIT（Expat）**；[上游 COPYING](https://github.com/json-c/json-c/blob/json-c-0.18-20240915/COPYING)。已有 [packaging/json-c-copyright](packaging/json-c-copyright) 保留版权、授权条款与免责声明，分发插件时应一并保留。 |
| [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx/tree/v1.13.7)，固定为 1.13.7 | Python 服务通过 `sherpa_onnx` API 运行流式 Zipformer、离线 SenseVoice 和标点恢复。该版本的 Python 包依赖同版本 `sherpa-onnx-core` 提供本机推理二进制。 | sherpa-onnx 项目采用 **Apache-2.0**；[上游 LICENSE](https://github.com/k2-fsa/sherpa-onnx/blob/v1.13.7/LICENSE)，随附[许可原文](licenses/sherpa-onnx-LICENSE.txt)。这项软件许可不代替模型权重或其内部第三方库的许可。 |
| [NumPy](https://numpy.org/)，声明范围 `>=1.26,<3`，本次核对版本 2.4.6 | Python 识别器将 PCM16 音频转换为浮点数组，并构造解码所需的音频缓冲区。 | NumPy 项目采用 **BSD-3-Clause**；[v2.4.6 LICENSE.txt](https://github.com/numpy/numpy/blob/v2.4.6/LICENSE.txt)，随附含 NumPy Developers 版权声明的[许可原文](licenses/numpy-LICENSE.txt)。 |

Fcitx5 版权记录原样来自 Ubuntu `libfcitx5core7` **5.1.19-1** 的 `/usr/share/doc/libfcitx5core7/copyright`；同版本 Config、Utils 软件包使用相同记录。该文件覆盖 Fcitx5 上游源码包的多个部分，其中出现的其他许可和文件范围不表示 LiltKey 捆绑了所有这些部分。当前插件使用系统共享库，用户可自行替换兼容的 Fcitx5 库并重编译插件；使用 LGPL 组件的权利及条件以随附许可为准。

当前 `.deb` 包分发原生插件和本项目服务源码，Python 第三方包由用户运行 setup 后安装，包内不捆绑 NumPy、sherpa-onnx 或其模型。Python wheel 可能包含其他第三方组件，例如 NumPy wheel 的 OpenBLAS；这些组件继续适用 wheel 自带的许可与声明。若另行分发整个虚拟环境或 wheel，应保留实际分发包中的全部许可证、版权和 NOTICE；本表是 LiltKey 集成组件清单，不是所有平台、所有传递依赖的完整清单。

## 系统音频与运行环境

音频采集通过子进程调用系统安装的 [GStreamer](https://gstreamer.freedesktop.org/)，诊断使用 `gst-inspect-1.0`。本次核对版本为 **1.28.2**，对应 Ubuntu 的 `gstreamer1.0-tools`、`gstreamer1.0-plugins-base` 和 `gstreamer1.0-plugins-good`。这些程序和插件不随 LiltKey 打包。

| 实际使用的工具或插件 | 用途与所属组件 | 上游许可依据 |
| --- | --- | --- |
| `gst-launch-1.0`、`gst-inspect-1.0`、`fdsink` | 启动/检查音频管道，将 PCM 写入服务读取的文件描述符；来自 GStreamer 核心与工具。 | LGPL 系列；`gst-launch`、`fdsink` 文件声明 **LGPL-2.0-or-later**，见 [gst-launch.c](https://github.com/GStreamer/gstreamer/blob/1.28.2/subprojects/gstreamer/tools/gst-launch.c)、[gstfdsink.c](https://github.com/GStreamer/gstreamer/blob/1.28.2/subprojects/gstreamer/plugins/elements/gstfdsink.c)。 |
| `audioconvert`、`audioresample` | 转换为单声道 16 kHz PCM16；来自 Base Plug-ins。 | 对应文件声明 **LGPL-2.0-or-later**，见 [gstaudioconvert.c](https://github.com/GStreamer/gstreamer/blob/1.28.2/subprojects/gst-plugins-base/gst/audioconvert/gstaudioconvert.c)、[gstaudioresample.c](https://github.com/GStreamer/gstreamer/blob/1.28.2/subprojects/gst-plugins-base/gst/audioresample/gstaudioresample.c)。 |
| `pulsesrc` | 从 PulseAudio 或 PipeWire 的 PulseAudio 兼容服务读取麦克风；来自 Good Plug-ins。 | **LGPL-2.1-or-later**，见 [pulsesrc.c](https://github.com/GStreamer/gstreamer/blob/1.28.2/subprojects/gst-plugins-good/ext/pulse/pulsesrc.c)。 |

GStreamer 各组件的许可证应按实际软件包和文件核对，项目许可说明见[官方 Licensing FAQ](https://gstreamer.freedesktop.org/documentation/frequently-asked-questions/licensing.html)。系统安装包的完整版权记录由发行版在 `/usr/share/doc/<软件包>/copyright` 提供。

其他环境要求包括 [Python](https://www.python.org/) **3.11 或更新版本**（[Python 许可与历史声明](https://docs.python.org/3.11/license.html)）、Linux 系统库、Fcitx5 桌面会话以及 systemd 用户服务。设备列表命令可调用系统 `pactl`。CMake 3.16+、C/C++ 编译器、pkg-config、setuptools 77.0.3+ 和 pip 用于构建或安装。这些工具由用户环境提供，本仓库不分发它们的副本。

## 模型、转换项目与参考资料

预训练模型的下载来源、固定版本、原始模型或转换项目及各自许可统一记录在 [MODEL_LICENSES.md](MODEL_LICENSES.md)。本项目下载并使用既有 ONNX 模型；模型来源或转换项目的许可证不能仅凭 sherpa-onnx 的 Apache-2.0 软件许可证推定。

上述上游链接同时用于 API、构建和使用方式的参考。列为依赖或参考资料不表示本项目复制了对应项目的源文件。本仓库若新增复制或改编的第三方代码，应就实际文件保留原作者声明，并在此补充具体来源、版本和适用许可。

## 许可文件来源

`licenses/` 下的软件许可原文按上表所链接的固定上游版本保存，未经改写。`Fcitx5-COPYRIGHT.txt` 为上述发行版版权记录；json-c 沿用 `packaging/json-c-copyright`。模型声明和原文位于 `MODEL_LICENSES.md` 与 `licenses/models/`，与软件许可分开保存。
