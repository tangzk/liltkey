# LiltKey 清透浅色主题

适用于 Fcitx5 经典用户界面，使用白色圆角面板、柔和阴影、蓝色圆角选中项、深灰文字与浅灰序号。横向候选词布局与较宽的内边距让拼音和语音状态更清楚。资源为项目原创，采用根目录 MIT 许可证；没有复用参考图中的品牌、图标或素材。

## 默认安装

从 deb **0.3.0-3** 起，安装包包含主题和字体推荐依赖；首次桌面配置时自动启用，源码安装也采用相同流程。原有默认浅色主题会迁移，已有自定义主题、默认深色主题或跟随系统深色的偏好保持不变；已有非默认字体和候选词排列方式保留。

升级时更新主题资源，但不会重置后来选择的主题、字体或已删除的经典界面配置。主题同时保存在用户目录中，卸载语音功能后仍可使用。

## 手动安装与选择

在项目根目录复制主题到用户目录：

```bash
mkdir -p "${XDG_DATA_HOME:-$HOME/.local/share}/fcitx5/themes"
cp -R themes/liltkey-light "${XDG_DATA_HOME:-$HOME/.local/share}/fcitx5/themes/"
```

打开“Fcitx 5 配置 → 附加组件 → 经典用户界面”，主题选 **LiltKey 清透浅色**。推荐字体 **Noto Sans CJK SC Medium 13**，取消“垂直候选列表”“跟随系统浅色/深色设置”和“使用系统的重点色”，保持参考样式的横向、浅色和蓝色高亮。修改后应用配置；主题尚未出现在列表时，关闭并重新打开配置工具。

主题会影响由经典界面绘制的拼音候选框、LiltKey 语音状态及经典菜单。系统托盘菜单可能由桌面环境自行绘制；Kimpanel 不使用这套主题。Wayland 下部分应用自行渲染候选框，已经打开的应用可能需要重新打开才能更新主题，Flatpak 应用还取决于沙箱能否读取主题文件。

这是静态候选框主题，不包含网页背景、品牌悬浮按钮、实时音量动画或背景毛玻璃。识别逻辑、快捷键、拼音词库与语音配置不变。

## 恢复与维护

首次迁移前已有的经典界面配置备份于 `~/.local/share/fcitx5-voice/theme-backup/classicui.conf`。初始化记录位于 `~/.local/share/fcitx5-voice/theme-default.json`；两者均遵守 `XDG_DATA_HOME`。该记录使后续安装不再覆盖外观选择。

在经典用户界面设置中选回“默认”主题并恢复原字体即可。若要完全还原，先备份 `~/.config/fcitx5/conf/classicui.conf`，恢复后重新加载经典界面配置。首次无此文件时，也应记录配置工具中原有的运行时设置。

PNG 使用九宫格拉伸保留圆角；半透明像素只用于阴影和边缘。安装不需要 Pillow；重建原始资源需要 Pillow，运行 `python3 themes/generate-assets.py`。`theme.conf` 的字段按 Fcitx5 5.1.19 验证。

参考：[Fcitx5 主题说明](https://fcitx-im.org/wiki/Theme_Customization/en)、[Fcitx5 5.1.19 主题字段](https://github.com/fcitx/fcitx5/blob/5.1.19/src/ui/classic/theme.h)。
