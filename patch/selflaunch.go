package main

// Windows 便携版自启动：双击 yingce.exe 即用，无需启动脚本。
// 仅在相关环境变量未设置时填默认值；脚本/服务方式启动不受影响
//（启动脚本会自行设置这些变量，并用 CANVAS_NO_BROWSER=1 关掉自动弹浏览器）。

import (
	"fmt"
	"log/slog"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"time"
)

const portablePort = "18789"

func exeDir() string {
	p, err := os.Executable()
	if err != nil {
		return ""
	}
	return filepath.Dir(p)
}

// applyPortableDefaults 仅在 Windows 下生效：把监听地址、数据目录、
// Agent 运行时目录、CORS 来源指向 exe 所在目录；已显式设置的环境变量不覆盖。
func applyPortableDefaults() {
	if runtime.GOOS != "windows" {
		return
	}
	dir := exeDir()
	if dir == "" {
		return
	}
	setDefault := func(key, value string) {
		if os.Getenv(key) == "" {
			os.Setenv(key, value)
		}
	}
	setDefault("CANVAS_BACKEND_ADDR", "127.0.0.1:"+portablePort)
	setDefault("CANVAS_BACKEND_DATA_DIR", filepath.Join(dir, "data"))
	setDefault("CANVAS_CORS_ORIGINS", "http://127.0.0.1:"+portablePort)
	setDefault("CANVAS_PI_RUNTIME_DIR", filepath.Join(dir, "agent-runtime", "pi"))
	// tools\node 与 tools\ffmpeg\bin 进 PATH（目录存在才加，保证 Agent/ffmpeg 能找到）。
	var prepend []string
	for _, rel := range []string{filepath.Join("tools", "node"), filepath.Join("tools", "ffmpeg", "bin")} {
		abs := filepath.Join(dir, rel)
		if st, err := os.Stat(abs); err == nil && st.IsDir() {
			prepend = append(prepend, abs)
		}
	}
	if len(prepend) > 0 {
		sep := string(os.PathListSeparator)
		os.Setenv("PATH", strings.Join(prepend, sep)+sep+os.Getenv("PATH"))
	}
}

// maybeOpenBrowser 在后端开始监听后自动打开浏览器。
// CANVAS_NO_BROWSER=1 时跳过（启动脚本自带等就绪逻辑，由脚本弹浏览器）。
func maybeOpenBrowser(addr string) {
	if runtime.GOOS != "windows" || os.Getenv("CANVAS_NO_BROWSER") != "" {
		return
	}
	url := browserURL(addr)
	if url == "" {
		return
	}
	go func() {
		time.Sleep(1500 * time.Millisecond)
		// rundll32 是打开默认浏览器最稳的方式，避开 start 命令的引号坑。
		cmd := exec.Command("rundll32", "url.dll,FileProtocolHandler", url)
		if err := cmd.Start(); err != nil {
			slog.Warn("无法自动打开浏览器", "url", url, "error", err)
			return
		}
		slog.Info("已在浏览器打开", "url", url)
		fmt.Printf("\n影策已启动：%s\n直接关闭本窗口即可停止服务。\n", url)
	}()
}

func browserURL(addr string) string {
	host := strings.TrimSpace(addr)
	if host == "" {
		return ""
	}
	if strings.HasPrefix(host, ":") {
		host = "127.0.0.1" + host
	}
	if !strings.Contains(host, "://") {
		host = "http://" + host
	}
	return host + "/"
}
