# 影策打包工程

> 作者：Passwd Word

把开源项目 [ddcat-ai/open-ai-canvas](https://github.com/ddcat-ai/open-ai-canvas)（影策 AI 影视创作工作台）打包成开箱即用的两种形态。所有构建都在 GitHub Actions 云端完成。

| 形态 | 产物 | 获取 |
|---|---|---|
| 🪟 Windows 便携版 | `yingce-portable-win64.zip`（解压双击 `yingce.exe` 即用，托盘常驻，无黑窗口） | [Releases](https://github.com/judy-gotv/open-ai-canvas-win/releases) |
| 🐳 Docker 版 | `ghcr.io/judy-gotv/open-ai-canvas:latest`（amd64 / arm64 / armv7 三架构） | [Packages](https://github.com/judy-gotv/open-ai-canvas-win/pkgs/container/open-ai-canvas) |

**与上游的区别**：内置视频任务 `/content` 回退修复——A6API 等 OpenAI Videos 风格中转渠道，任务完成后自动从 `/v1/videos/{id}/content` 拉取视频（上游声明式协议插件缺这一步，会导致"已完成但没有返回结果"）。详见 `patch/patch_video.py`。

---

## 🐳 Docker 版部署（服务器）

```bash
docker run -d \
  --name yingce \
  --restart unless-stopped \
  -p 8080:8080 \
  -v yingce-data:/data \
  ghcr.io/judy-gotv/open-ai-canvas:latest
```

浏览器打开 `http://服务器IP:8080` 即可使用。

### docker-compose（推荐）

```yaml
services:
  yingce:
    image: ghcr.io/judy-gotv/open-ai-canvas:latest
    container_name: yingce
    restart: unless-stopped
    ports:
      - "8080:8080"
    volumes:
      - ./data:/data
    environment:
      - CANVAS_REGISTRATION_ENABLED=false   # 注册开关，默认关闭
      # - CANVAS_DATABASE_DRIVER=postgres    # 默认 sqlite；用 postgres 时取消注释
      # - DATABASE_URL=postgres://user:pass@host:5432/yingce?sslmode=disable
```

```bash
docker compose up -d
```

### 要点

- **数据**：所有数据（数据库、上传文件）都在容器内 `/data`，务必挂载 volume，否则删容器数据就没了。
- **升级**：`docker compose pull && docker compose up -d`，volume 里的数据保留。
- **架构**：Docker 自动拉取对应架构（x86 服务器 / ARM 服务器 / 树莓派 32 位），无需手动指定。
- **反代**：生产环境建议前面加 Nginx/Caddy 做 HTTPS，容器本身只监听 8080。

### 常用环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `CANVAS_BACKEND_ADDR` | `:8080` | 监听地址 |
| `CANVAS_BACKEND_DATA_DIR` | `/data` | 数据目录 |
| `CANVAS_REGISTRATION_ENABLED` | `false` | 是否开放注册 |
| `CANVAS_DATABASE_DRIVER` | `sqlite` | `sqlite` 或 `postgres` |
| `DATABASE_URL` | — | postgres 连接串 |
| `CANVAS_LOG_LEVEL` | `info` | `debug` / `info` / `warn` / `error` |

---

## 🪟 Windows 便携版部署（个人电脑）

1. 从 [Releases](https://github.com/judy-gotv/open-ai-canvas-win/releases) 下载最新 `yingce-portable-win64.zip`。
2. 解压到任意目录（路径不要有中文）。
3. 双击 `yingce.exe`——托盘出现图标，浏览器自动打开 `http://127.0.0.1:18789`。
4. 数据在包内 `data/` 目录。

**升级**：先退出旧版（托盘右键退出），把旧包 `data/` 目录拷出来，解压新包后拷回去，再启动。

---

## 🔧 构建说明（给维护者）

### 补丁系统

不 fork 上游，每次构建按固定顺序打补丁再编译（上游更新后补丁自动重新应用）：

1. 全新 checkout 上游源码 → 2. 拷入 `patch/` → 3. `patch_main.py`（Windows，main.go 5 处）→ 4. `patch_video.py`（视频修复 7 处，Windows/Docker 共用）→ 5. 编译打包

- 每个锚点断言恰好命中 1 次，打不上则构建直接失败（不静默出坏包）。
- 补丁脚本输出文案必须纯 ASCII（Windows runner 是 cp1252）。

### 工作流

| 工作流 | 触发 | 产物 |
|---|---|---|
| 构建 Windows 便携版 | 手动 / `win-v*` 标签 | Release zip |
| 构建 Docker 镜像 | 手动 / `docker/`、`patch/` 推送 | GHCR 多架构镜像 |
| 上游自动跟踪 | 每 6 小时 | 上游有新提交时自动构建发版 |
