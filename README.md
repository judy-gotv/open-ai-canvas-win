# 影策 Windows 便携版打包工程

把开源项目 [ddcat-ai/open-ai-canvas](https://github.com/ddcat-ai/open-ai-canvas)（影策 AI 影视创作工作台）
打成 Windows 绿色免安装包的构建工程。产物：`yingce-portable-win64.zip`，
解压后双击 `yingce.exe` 即用（自动配好数据目录、端口并弹浏览器），
无需安装 Node / Python / 数据库；「启动影策.bat」为备用启动方式。

## 用法

### 一键构建（推荐）

1. 在本仓库的 GitHub 页面点 **Actions → 构建 Windows 便携版 → Run workflow**
   （可指定上游 commit / tag，默认 `dc035d5`）。
2. 构建完成后在 Artifacts 下载 `yingce-portable-win64.zip`。
3. 推送 `win-v*` 标签会自动发版（Release 带 zip 附件）。

### 构建内容

- 上游 Go 后端 + 两个小补丁：`patch/webstatic.go` 把前端 `dist` 直接 embed
  进 `yingce.exe`，单个 exe 同时提供 Web UI 与 `/api`，无需 nginx；
  `patch/selflaunch.go` 让 exe 双击自启动（自动配 data 目录/端口/PATH 并弹浏览器）。
- 前端：`bun install --frozen-lockfile` + `vite build`（与官方 Dockerfile 同口径）。
- 后端：`windows/amd64` + CGO（mingw-w64 编译 sqlite）。
- 附带：便携版 Node.js 22（画布 Agent 用）、ffmpeg（视频转码/字幕转写）、
  Agent 运行时（含 `npm ci` 依赖）、官方 `plugin-packages` 插件包。

### 目录说明

```
repo/
  .github/workflows/build.yml   构建流水线
  patch/webstatic.go            前端嵌入补丁（workflow 自动应用到上游源码）
  portable/                     启动/停止脚本与使用说明（打进 zip）
```

## 本地验证补丁逻辑

补丁本身很小（一个 NoRoute 处理器）：非 `/api` 请求先找嵌入的静态文件，
命中则直接返回；无扩展名路径回退到 `index.html`（SPA）；其余交还给上游
原有的短链代理处理器，业务路由与 `/api/*` 行为零变化。

## 作者

Passwd Word
