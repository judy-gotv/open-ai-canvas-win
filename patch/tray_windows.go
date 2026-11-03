//go:build windows

package main

// Windows 托盘版：无控制台窗口的"真正桌面应用"体验。
// 双击 yingce.exe → 托盘出现图标 → 自动弹浏览器；右键托盘可打开页面、
// 查看日志、退出。日志同时落盘到 <data>/yingce.log（无窗口后控制台不可见）。
//
// 配合构建参数 -ldflags "-H=windowsgui" 使用（见 workflow）。

import (
	"context"
	_ "embed"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/getlantern/systray"
	"golang.org/x/sys/windows"
	"yingce/backend/internal/logging"
)

//go:embed trayicon.ico
var trayIconICO []byte

// useTray 是否启用托盘模式（Windows 默认开，CANVAS_NO_TRAY=1 可关）。
func useTray() bool {
	return os.Getenv("CANVAS_NO_TRAY") == ""
}

// setupPortableLogging 把日志同时写进 <dataDir>/yingce.log。
// 在 main() 里 logging.Setup 之前调用，保留上游的日志配置只换 Output。
func setupPortableLogging(cfg *logging.Config) {
	dir := os.Getenv("CANVAS_BACKEND_DATA_DIR")
	if dir == "" {
		if d := exeDir(); d != "" {
			dir = filepath.Join(d, "data")
		}
	}
	if dir == "" {
		return
	}
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return
	}
	f, err := os.OpenFile(filepath.Join(dir, "yingce.log"), os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)
	if err != nil {
		return
	}
	cfg.Output = io.MultiWriter(os.Stderr, f)
}

// maybeHandleAlreadyRunning 若本机便携地址已有 HTTP 200 响应，视为影策已在
// 运行：直接打开浏览器后静默退出，避免重复启动报端口占用。
func maybeHandleAlreadyRunning(addr string) {
	url := browserURL(addr)
	if url == "" {
		return
	}
	client := &http.Client{Timeout: 2 * time.Second}
	resp, err := client.Get(url)
	if err != nil {
		return
	}
	resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return
	}
	openBrowserNow(url)
	os.Exit(0)
}

// openLogFile 用记事本打开日志文件。
func openLogFile() {
	dir := os.Getenv("CANVAS_BACKEND_DATA_DIR")
	if dir == "" {
		if d := exeDir(); d != "" {
			dir = filepath.Join(d, "data")
		}
	}
	if dir == "" {
		return
	}
	p := filepath.Join(dir, "yingce.log")
	if f, err := os.OpenFile(p, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644); err == nil {
		f.Close()
	}
	exec.Command("notepad.exe", p).Start()
}

// fatalError 无窗口模式下的致命错误：弹框提示后退出。
func fatalError(err error) {
	msg := "影策启动失败：\n" + err.Error()
	if s := err.Error(); strings.Contains(s, "bind") || strings.Contains(s, "address already in use") {
		msg = "影策启动失败：端口已被占用。\n\n如果影策已在运行，无需重复启动；\n否则请关闭占用该端口的程序后重试。"
	}
	title, _ := windows.UTF16PtrFromString("影策")
	text, _ := windows.UTF16PtrFromString(msg)
	windows.MessageBox(0, text, title, windows.MB_OK|windows.MB_ICONERROR)
	os.Exit(1)
}

// trayMainLoop 在主线程跑托盘消息循环，直到退出/服务异常/ctx 取消。
// 返回值语义与原 select 块一致：serveFailure（nil 表示正常退出）。
func trayMainLoop(ctx context.Context, serveErr chan error, pageURL string) error {
	var once sync.Once
	quit := func() { once.Do(func() { systray.Quit() }) }
	reason := make(chan error, 1)
	setReason := func(err error) {
		select {
		case reason <- err:
		default:
		}
	}

	// 后台盯住 ctx 与 HTTP 服务，任一结束就退出托盘循环。
	go func() {
		select {
		case <-ctx.Done():
			setReason(nil)
		case err := <-serveErr:
			if err != nil && !errors.Is(err, http.ErrServerClosed) {
				setReason(fmt.Errorf("HTTP 服务异常退出：%w", err))
			} else {
				setReason(nil)
			}
		}
		quit()
	}()

	systray.Run(
		func() {
			if len(trayIconICO) > 0 {
				systray.SetIcon(trayIconICO)
			}
			systray.SetTitle("影策")
			systray.SetTooltip("影策 - AI 创作画布")
			mOpen := systray.AddMenuItem("打开影策", "在浏览器中打开影策")
			mLog := systray.AddMenuItem("查看日志", "用记事本打开运行日志")
			systray.AddSeparator()
			mQuit := systray.AddMenuItem("退出", "停止服务并退出影策")
			go func() {
				for {
					select {
					case <-mOpen.ClickedCh:
						openBrowserNow(pageURL)
					case <-mLog.ClickedCh:
						openLogFile()
					case <-mQuit.ClickedCh:
						setReason(nil)
						quit()
						return
					}
				}
			}()
		},
		func() { setReason(nil) },
	)
	select {
	case err := <-reason:
		return err
	default:
		return nil
	}
}
