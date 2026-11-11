# 影策 Docker 版：单镜像（前端嵌入后端），多架构。
# 构建 context 为打包仓库根目录，上游源码在 upstream/ 子目录。
# 构建：docker buildx build --platform linux/amd64,linux/arm64,linux/arm/v7
# 作者：Passwd Word

# syntax=docker/dockerfile:1.7

# ---------- 阶段1：前端构建（架构无关，产物为静态文件） ----------
FROM --platform=$BUILDPLATFORM oven/bun:1.3.9 AS web-build

WORKDIR /app/web
COPY upstream/web/package.json upstream/web/bun.lock ./
RUN bun install --frozen-lockfile
COPY upstream/VERSION /app/VERSION
COPY upstream/CHANGELOG.md /app/CHANGELOG.md
COPY upstream/README.md /app/README.md
COPY upstream/assets /app/assets
COPY upstream/web ./
# 前端有文件 import 后端目录的 JSON（如 platform-knowledge.ts → backend/internal/ecommerceagent/，
# skin.ts → backend/internal/app/appearance_theme_packs.json），需一并拷入否则 vite 报 UNRESOLVED_IMPORT
COPY upstream/backend/internal/ecommerceagent/platform_knowledge.json /app/backend/internal/ecommerceagent/platform_knowledge.json
COPY upstream/backend/internal/app/appearance_theme_packs.json /app/backend/internal/app/appearance_theme_packs.json
ARG BUILD_VERSION
ARG BUILD_COMMIT=unknown
ARG BUILD_TIME=unknown
ENV CANVAS_BUILD_VERSION=${BUILD_VERSION}
ENV CANVAS_BUILD_COMMIT=${BUILD_COMMIT}
ENV CANVAS_BUILD_TIME=${BUILD_TIME}
RUN bun --bun ./node_modules/vite/bin/vite.js build

# ---------- 阶段2：后端交叉编译（含补丁） ----------
FROM --platform=$BUILDPLATFORM golang:1.25-bookworm AS backend-build

ARG TARGETARCH
ARG TARGETVARIANT
ARG GOPROXY=https://proxy.golang.org,direct
ENV GOPROXY=$GOPROXY

# CGO 交叉工具链（sqlite 需要 C 编译器；libc6-dev-*-cross 提供目标平台头文件）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc-aarch64-linux-gnu libc6-dev-arm64-cross \
    gcc-arm-linux-gnueabihf libc6-dev-armhf-cross \
    python3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src/backend
COPY upstream/backend/go.mod upstream/backend/go.sum ./
# go.mod 含本地 replace，需先复制 third_party 让依赖解析通过
COPY upstream/backend/third_party ./third_party
RUN go mod download
COPY upstream/backend ./
COPY upstream/VERSION /src/VERSION

# 前端嵌入：把 web/dist 放到 cmd/server/webdist，用 webstatic.go 提供 Web UI
COPY --from=web-build /app/web/dist /src/backend/cmd/server/webdist/
COPY patch/webstatic.go /src/backend/cmd/server/webstatic.go
# 打补丁：main.go 接入前端嵌入（仅 webstatic，不含托盘/自启动）+ 视频 /content 修复
COPY patch/patch_docker_main.py patch/patch_video.py /tmp/
RUN python3 /tmp/patch_docker_main.py /src/backend/cmd/server/main.go \
 && python3 /tmp/patch_video.py /src

# 按目标架构交叉编译（CGO 开启，sqlite 用）
ARG BUILD_VERSION
ARG BUILD_COMMIT=unknown
ARG BUILD_TIME=unknown
RUN set -eu; \
    case "${TARGETARCH}" in \
      amd64) CC_NAME=gcc; GOARCH_VAL=amd64; ;; \
      arm64) CC_NAME=aarch64-linux-gnu-gcc; GOARCH_VAL=arm64; ;; \
      arm)   CC_NAME=arm-linux-gnueabihf-gcc; GOARCH_VAL=arm; ;; \
      *) echo "unsupported arch: ${TARGETARCH}" >&2; exit 1; ;; \
    esac; \
    if [ "${TARGETARCH}" = "arm" ]; then export GOARM="${TARGETVARIANT#v}"; fi; \
    version="${BUILD_VERSION:-$(tr -d '\r\n' </src/VERSION)}"; \
    ldflags="-s -w -X yingce/backend/internal/buildinfo.Version=${version} -X yingce/backend/internal/buildinfo.Commit=${BUILD_COMMIT} -X yingce/backend/internal/buildinfo.BuildTime=${BUILD_TIME}"; \
    CGO_ENABLED=1 GOOS=linux GOARCH="${GOARCH_VAL}" CC="${CC_NAME}" \
      go build -trimpath -ldflags="${ldflags}" -o /out/yingce-backend ./cmd/server

# ---------- 阶段3：运行镜像 ----------
FROM alpine:3.22

# ffmpeg：视频处理（抽帧/转码）需要；ca-certificates：上游 HTTPS 需要
RUN apk add --no-cache ca-certificates tzdata ffmpeg \
    && addgroup -S app \
    && adduser -S app -G app

WORKDIR /app
ENV GIN_MODE=release
ENV CANVAS_BACKEND_ADDR=:8080
ENV CANVAS_BACKEND_DATA_DIR=/data

RUN mkdir -p /data && chown -R app:app /data
COPY --from=backend-build /out/yingce-backend /usr/local/bin/yingce-backend

USER app
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD wget -qO- http://127.0.0.1:8080/api/health/ready >/dev/null || exit 1

CMD ["yingce-backend"]
