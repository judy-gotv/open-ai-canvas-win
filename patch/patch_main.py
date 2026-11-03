# 给 upstream backend/cmd/server/main.go 打便携版补丁。
# 用法：python patch_main.py <main.go 路径>
# 写成独立文件，避免 PowerShell 下 python -c 的多层引号转义坑。

import sys

path = sys.argv[1]
s = open(path, encoding="utf-8").read()

T = "\t"
N = "\n"

subs = [
    # 1. 前端嵌入：NoRoute 改走 registerWebStatic（webstatic.go）
    ("r.NoRoute(handler.SystemProxyNoRouteHandler(svc))",
     "registerWebStatic(r, handler.SystemProxyNoRouteHandler(svc))"),

    # 2. 双击自启动：run() 开头应用便携版默认值（selflaunch.go）
    ('dataDir := env("CANVAS_BACKEND_DATA_DIR", "data")',
     "applyPortableDefaults()" + N + T + 'dataDir := env("CANVAS_BACKEND_DATA_DIR", "data")'),

    # 3. 双击自启动：监听成功后自动弹浏览器（selflaunch.go）
    ('slog.Info("backend listening", "addr", addr)',
     'slog.Info("backend listening", "addr", addr)' + N + T + "maybeOpenBrowser(addr)"),

    # 4. 托盘版：日志同时落盘到 <data>/yingce.log（tray_windows.go；
    #    无窗口后控制台不可见，保留上游日志配置只换 Output）
    (T + "logging.Setup(logConfig)",
     T + "setupPortableLogging(&logConfig)" + N + T + "logging.Setup(logConfig)"),

    # 5. 托盘版：Windows 下主线程跑托盘消息循环，代替原来的 select 等待；
    #    非 Windows 保持原行为（tray_windows.go / tray_other.go）
    (T + "var serveFailure error" + N
     + T + "select {" + N
     + T + "case <-ctx.Done():" + N
     + T + "case err := <-serveErr:" + N
     + T + T + "if err != nil && !errors.Is(err, http.ErrServerClosed) {" + N
     + T + T + T + 'serveFailure = fmt.Errorf("HTTP 服务异常退出：%w", err)' + N
     + T + T + "}" + N
     + T + "}",
     T + "var serveFailure error" + N
     + T + "if useTray() {" + N
     + T + T + "serveFailure = trayMainLoop(ctx, serveErr, browserURL(addr))" + N
     + T + "} else {" + N
     + T + T + "select {" + N
     + T + T + "case <-ctx.Done():" + N
     + T + T + "case err := <-serveErr:" + N
     + T + T + T + "if err != nil && !errors.Is(err, http.ErrServerClosed) {" + N
     + T + T + T + T + 'serveFailure = fmt.Errorf("HTTP 服务异常退出：%w", err)' + N
     + T + T + T + "}" + N
     + T + T + "}" + N
     + T + "}"),

    # 6. 托盘版：致命错误弹框提示（无窗口时 log.Fatal 没人看得见）
    (T + "if err := run(ctx); err != nil {" + N
     + T + T + "log.Fatal(err)" + N
     + T + "}",
     T + "if err := run(ctx); err != nil {" + N
     + T + T + "fatalError(err)" + N
     + T + "}"),
]

for i, (old, new) in enumerate(subs, 1):
    n = s.count(old)
    assert n == 1, "anchor #%d not unique/found (count=%d): %r" % (i, n, old[:80])
    s = s.replace(old, new)

open(path, "w", encoding="utf-8", newline="").write(s)
print("main.go patched (%d anchors)" % len(subs))
