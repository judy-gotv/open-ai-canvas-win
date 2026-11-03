# 给 upstream backend/cmd/server/main.go 打 Docker 版补丁（仅前端嵌入）。
# 用法：python patch_docker_main.py <main.go 路径>
# Docker 单镜像版不需要托盘/双击自启动/自动弹浏览器，只要 webstatic.go 的前端嵌入。
# 写成独立文件，避免 PowerShell 下 python -c 的多层引号转义坑。
#
# Author: Passwd Word

import sys

path = sys.argv[1]
s = open(path, encoding="utf-8").read()

T = "\t"
N = "\n"

subs = [
    # 前端嵌入：NoRoute 改走 registerWebStatic（webstatic.go，与 Windows 便携版同文件）
    ("r.NoRoute(handler.SystemProxyNoRouteHandler(svc))",
     "registerWebStatic(r, handler.SystemProxyNoRouteHandler(svc))"),
]

for i, (old, new) in enumerate(subs):
    n = s.count(old)
    # 注意：输出文案必须纯 ASCII，Windows runner cp1252 下中文会 UnicodeEncodeError
    assert n == 1, "main.go anchor #%d hit %d times (expected 1)" % (i + 1, n)
    s = s.replace(old, new)

open(path, "w", encoding="utf-8").write(s)
print("main.go patched (%d anchors)" % len(subs))
