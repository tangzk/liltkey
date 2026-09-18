# LiltKey 宣传页

英文为默认语言的产品介绍页（中文版位于 `/zh/`），包含品牌介绍、文字动画演示、真实 Fcitx5 主题截图、核心功能、快捷键指南、`.deb` 下载与自动安装说明和常见问题。源码安装作为替代入口链接到开发指南。

v0.4.0 的首页提示、演示状态和使用指南以长按 Ctrl+Alt 录音、松开结束为主，保留 Ctrl+Alt+V 切换方式，并明确只有切换方式受默认 30 秒上限限制。下载按钮、版本标识及安装命令与根 README 和发布包同步。

## 本地预览

在项目根目录运行：

```bash
python3 -m http.server 8080 --bind 127.0.0.1 --directory website/dist
```

打开 <http://127.0.0.1:8080>。页面为静态 HTML、CSS、JavaScript，无需安装前端依赖。输入过程演示只播放预设文字动画，不会访问麦克风。

## 文件

- `dist/index.html`：英文首页（默认语言），含 Google Search Console 与 Bing 站点验证标签，移动或替换首页时必须保留。插件界面与通知目前仅有中文，演示中的状态浮层保持中文，并在 FAQ 中说明。
- `dist/zh/index.html`：中文版，区块与英文首页一一对应，共用样式、脚本和图片。修改任一语言的功能、版本或 FAQ 时需同步另一语言。
- `dist/en/index.html`：旧英文地址的跳转页，立即跳到首页；保留它以免已分享的 `/en/` 链接失效。
- `dist/styles.css`：桌面与移动端样式，包含减少动画偏好支持。
- `dist/motion.css`：声波、标题流光、按钮和快捷键动效，包含减少动态偏好与手动暂停样式。
- `dist/app.js`：渐入、演示与复制命令；复制失败时选中文字供手动复制。界面文案按 `<html lang>` 切换：以 `zh` 开头用中文，其余默认英文。
- `dist/favicon.svg`：站点图标。
- `dist/sitemap.xml`：站点地图，已提交至 Google Search Console 与 Bing Webmaster Tools；新增页面时需同步。
- `dist/llms.txt`：面向 AI 检索的站点摘要与文档索引；版本号、下载地址和能力说明需与页面同步。
- `dist/assets/fcitx5-light-theme.png`：与根 README 同步的真实 Fcitx5 截图，来源和拍摄说明见 [截图记录](../docs/assets/README.md)。
- `.openai/hosting.json`：Sites 托管配置。

安装区以下载按钮为主入口，自动配置说明与首次使用提示直接可见；终端安装命令作为折叠的可选方式，不再把等待初始化与重新登录列为编号安装步骤。

功能区展示清透浅色主题的默认安装、个人外观偏好保留与升级行为。完整截图按比例显示，可打开原图；它来自真实 Fcitx5 拼音候选框和 X11 测试文本框。首页动画复现截图中的文本框与横向拼音候选栏，再切换到语音临时文字和原生状态浮层。面板、蓝色选中项、翻页箭头直接复用 `themes/liltkey-light/` 的 PNG，使用相同的九宫格边距保留圆角与阴影；网站副本位于 `dist/assets/liltkey-light/`，修改主题资源时需同步。输入框内不添加声波、标签或播放按钮。播放控制位于输入区之外，演示明确标注为示意，不是真实录屏。

维护页面时，以根目录 [README](../README.md)（英文）和 [README.zh-CN](../README.zh-CN.md)（中文）为安装与能力说明的依据。产品名称为 LiltKey，现有命令仍为 `fcitx5-voice`。

页面在演示卡进入视口后循环播放文字输入示意：展示拼音候选、提交选中词、切换到逐字语音预编辑、补充标点并提交、停留后重新开始；不会访问麦克风。卡片按钮可暂停或继续演示，右上角按钮可暂停页面全部动效，后者的偏好保存在当前浏览器。系统开启“减少动态效果”时跳过自动演示和入场动画。离开视口或切到后台时停止当前演示，返回后恢复循环；主动暂停的演示保持暂停。直接访问安装锚点、键盘聚焦及 JavaScript 不可用时，正文保持可读。

不支持 `IntersectionObserver` 的旧浏览器提供手动单次播放，避免在无法判断视口时自动循环。

用 Node.js 内置测试运行器验证循环播放、暂停、可见性与减少动态效果：

```bash
node --test website/tests/demo-loop.test.cjs
```

## GitHub Pages

宣传页目标地址：<https://tangzk.github.io/liltkey/>（英文），中文版 <https://tangzk.github.io/liltkey/zh/>。

- 项目代码与宣传页统一维护在 `tangzk/liltkey`，不再向 `liltkey-site` 同步页面。
- 在仓库 **Settings → Pages → Build and deployment** 中，将发布源设为 **GitHub Actions**。GitHub Free 使用此方案时需要公开仓库。
- [发布流程](../.github/workflows/pages.yml) 在 `main` 的页面或许可文件更新时运行，也支持手动触发。
- 仅上传 `website/dist/` 内的静态页面文件和根目录 MIT `LICENSE`；项目代码、模型、配置及 `.openai/hosting.json` 不进入网页发布产物。
- 样式、脚本和图标使用相对路径，适配 `/liltkey/` 子路径。页面 canonical 和根 README 的入口需与此地址一致。
- 第一次部署前须启用 Pages；发布成功后可在 Actions 中查看实际页面地址。
- 仓库仍为私有时流程跳过发布；改为公开并启用 Pages 后，手动运行一次 **Deploy LiltKey Pages** 即可首次发布。
- `.openai/hosting.json` 保留先前 Sites 预览的关联，不用于 GitHub Pages 发布。
