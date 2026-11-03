# 给 upstream backend/cmd/server/main.go 打便携版补丁。
# 用法：python patch_main.py <main.go 路径>
# 写成独立文件，避免 PowerShell 下 python -c 的多层引号转义坑。

import sys

path = sys.argv[1]
s = open(path, encoding="utf-8").read()

subs = [
    # 1. 前端嵌入：NoRoute 改走 registerWebStatic（webstatic.go）
    ("r.NoRoute(handler.SystemProxyNoRouteHandler(svc))",
     "registerWebStatic(r, handler.SystemProxyNoRouteHandler(svc))"),
    # 2. 双击自启动：run() 开头应用便携版默认值（selflaunch.go）
    ('dataDir := env("CANVAS_BACKEND_DATA_DIR", "data")',
     'applyPortableDefaults()\n\tdataDir := env("CANVAS_BACKEND_DATA_DIR", "data")'),
    # 3. 双击自启动：监听成功后自动弹浏览器（selflaunch.go）
    ('slog.Info("backend listening", "addr", addr)',
     'slog.Info("backend listening", "addr", addr)\n\tmaybeOpenBrowser(addr)'),
]

for old, new in subs:
    n = s.count(old)
    assert n == 1, "anchor not unique/found: %r (count=%d)" % (old, n)
    s = s.replace(old, new)

open(path, "w", encoding="utf-8", newline="").write(s)
print("main.go patched (3 anchors)")
