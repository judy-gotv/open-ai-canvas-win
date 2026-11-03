//go:build !windows

package main

// 非 Windows 平台：托盘相关全部退化为原有行为（控制台 + 信号）。

import (
	"context"
	"log"

	"yingce/backend/internal/logging"
)

func useTray() bool { return false }

func trayMainLoop(ctx context.Context, serveErr chan error, pageURL string) error {
	return nil // 不可达：非 Windows 下 useTray() 恒为 false
}

func maybeHandleAlreadyRunning(addr string) {}

func setupPortableLogging(_ *logging.Config) {}

func fatalError(err error) { log.Fatal(err) }
