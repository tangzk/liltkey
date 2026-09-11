# LiltKey 宣传页

中文产品介绍页，包含品牌介绍、文字动画演示、核心功能、快捷键指南、`.deb` 下载与安装步骤和常见问题。源码安装作为替代入口链接到主项目 README。

## 本地预览

在项目根目录运行：

```bash
python3 -m http.server 8080 --bind 127.0.0.1 --directory website/dist
```

打开 <http://127.0.0.1:8080>。页面为静态 HTML、CSS、JavaScript，无需安装前端依赖。输入过程演示只播放预设文字动画，不会访问麦克风。

## 文件

- `dist/index.html`：页面内容与安装命令。
- `dist/styles.css`：桌面与移动端样式，包含减少动画偏好支持。
- `dist/motion.css`：声波、标题流光、按钮和快捷键动效，包含减少动态偏好与手动暂停样式。
- `dist/app.js`：渐入、演示与复制命令；复制失败时选中文字供手动复制。
- `dist/favicon.svg`：站点图标。
- `.openai/hosting.json`：Sites 托管配置。

维护页面时，以根目录 [README](../README.md) 为安装与能力说明的依据。产品名称为 LiltKey，现有命令仍为 `fcitx5-voice`。

页面在演示卡进入视口后自动播放一次文字输入示意，仍可手动重播；不会访问麦克风。右上角按钮可暂停页面动效，偏好保存在当前浏览器。系统开启“减少动态效果”时跳过自动演示和入场动画。离开视口或切到后台时停止当前演示；直接访问安装锚点、键盘聚焦及 JavaScript 不可用时，正文保持可读。

## GitHub Pages

宣传页目标地址：<https://tangzk.github.io/liltkey/>。

- 项目代码与宣传页统一维护在 `tangzk/liltkey`，不再向 `liltkey-site` 同步页面。
- 在仓库 **Settings → Pages → Build and deployment** 中，将发布源设为 **GitHub Actions**。GitHub Free 使用此方案时需要公开仓库。
- [发布流程](../.github/workflows/pages.yml) 在 `main` 的页面或许可文件更新时运行，也支持手动触发。
- 仅上传 `website/dist/` 内的静态页面文件和根目录 MIT `LICENSE`；项目代码、模型、配置及 `.openai/hosting.json` 不进入网页发布产物。
- 样式、脚本和图标使用相对路径，适配 `/liltkey/` 子路径。页面 canonical 和根 README 的入口需与此地址一致。
- 第一次部署前须启用 Pages；发布成功后可在 Actions 中查看实际页面地址。
- 仓库仍为私有时流程跳过发布；改为公开并启用 Pages 后，手动运行一次 **Deploy LiltKey Pages** 即可首次发布。
- `.openai/hosting.json` 保留先前 Sites 预览的关联，不用于 GitHub Pages 发布。
