# LiltKey 宣传页

中文产品介绍页，包含品牌介绍、文字动画演示、核心功能、快捷键指南、源码安装步骤和常见问题。

## 本地预览

在项目根目录运行：

```bash
python3 -m http.server 8080 --bind 127.0.0.1 --directory website/dist
```

打开 <http://127.0.0.1:8080>。页面为静态 HTML、CSS、JavaScript，无需安装前端依赖。输入过程演示只播放预设文字动画，不会访问麦克风。

## 文件

- `dist/index.html`：页面内容与安装命令。
- `dist/styles.css`：桌面与移动端样式，包含减少动画偏好支持。
- `dist/app.js`：演示与复制命令；复制失败时选中文字供手动复制。
- `dist/favicon.svg`：站点图标。
- `.openai/hosting.json`：Sites 托管配置。

维护页面时，以根目录 [README](../README.md) 为安装与能力说明的依据。产品名称为 LiltKey，现有命令仍为 `fcitx5-voice`。

## GitHub Pages

公开宣传页地址：<https://tangzk.github.io/liltkey-site/>。

- 项目完整代码与历史保存在私有仓库 `tangzk/liltkey`。
- 公开仓库 `tangzk/liltkey-site` 只接收 `dist/` 内的静态页面文件（包括 `.nojekyll`）。
- Pages 发布源设置为 `main` 分支的根目录 `/`。
- 更新时将 `website/dist/` 的内容同步至公开仓库根目录，提交并推送；不要复制主仓库、历史、模型、配置或 `.openai/hosting.json`。
- `.openai/hosting.json` 保留先前 Sites 预览的关联，不用于 GitHub Pages 发布。
