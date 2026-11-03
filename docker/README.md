# 影策 Docker 版使用说明

> 作者：Passwd Word

单镜像版影策（前端已嵌入后端），一个容器同时提供 Web UI 与 `/api`。支持 `linux/amd64`、`linux/arm64`、`linux/arm/v7`（32 位 ARM）。

镜像地址：`ghcr.io/judy-gotv/open-ai-canvas:latest`

**与上游的区别**：内置视频任务 `/content` 回退修复（A6API 等 OpenAI Videos 风格中转，任务完成后自动从 `/v1/videos/{id}/content` 拉取视频，详见打包仓库 `patch/patch_video.py`）。

## 快速启动

```bash
docker run -d \
  --name yingce \
  --restart unless-stopped \
  -p 8080:8080 \
  -v yingce-data:/data \
  ghcr.io/judy-gotv/open-ai-canvas:latest
```

浏览器打开 `http://服务器IP:8080` 即可使用。

## docker-compose（推荐）

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
      # 注册开关（默认关闭，按需打开）
      - CANVAS_REGISTRATION_ENABLED=false
      # 数据库：默认 sqlite（数据在 /data）；也可用 postgres
      # - CANVAS_DATABASE_DRIVER=postgres
      # - DATABASE_URL=postgres://user:pass@host:5432/yingce?sslmode=disable
```

```bash
docker compose up -d
```

## 数据说明

- 所有数据（SQLite 数据库、上传文件、日志）都在容器内 `/data`，务必挂载 volume，否则删容器数据就没了。
- 升级：`docker compose pull && docker compose up -d` 即可，volume 里的数据保留。

## 常用环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `CANVAS_BACKEND_ADDR` | `:8080` | 监听地址 |
| `CANVAS_BACKEND_DATA_DIR` | `/data` | 数据目录 |
| `CANVAS_REGISTRATION_ENABLED` | `false` | 是否开放注册 |
| `CANVAS_DATABASE_DRIVER` | `sqlite` | `sqlite` 或 `postgres` |
| `DATABASE_URL` | — | postgres 连接串（driver=postgres 时用） |
| `CANVAS_LOG_LEVEL` | `info` | `debug` / `info` / `warn` / `error` |
| `GIN_MODE` | `release` | 不要改 |

## 架构支持

| 平台 | 说明 |
|---|---|
| `linux/amd64` | x86_64 服务器 / PC |
| `linux/arm64` | ARM64 服务器（如腾讯云 ARM、树莓派 4/5 64 位系统） |
| `linux/arm/v7` | 32 位 ARM（如树莓派 32 位系统） |

Docker 会自动拉取对应架构的镜像，无需手动指定。

## 自行构建

```bash
# 打包仓库根目录执行（需先 git clone 打包仓库，上游源码会自动检出）
docker buildx build \
  --platform linux/amd64,linux/arm64,linux/arm/v7 \
  -f docker/Dockerfile \
  -t yingce:local .
```

> 构建顺序遵循统一规范：fresh 上游源码 → 拷入补丁 → `patch_docker_main.py`（前端嵌入）→ `patch_video.py`（视频修复 7 处）→ 前端构建 → Go 交叉编译。详见 `docker/Dockerfile`。
