package main

// Windows 便携包：把前端构建产物 (web/dist) 直接 embed 进后端可执行文件，
// 单个 exe 即可同时提供 Web UI 与 /api，无需 nginx 或额外静态服务器。
//
// 构建时把 web/dist 复制到本目录下的 webdist/ 即可；
// 目录不存在或为空时自动退化为原有行为（仅短链代理 NoRoute）。

import (
	"embed"
	"io/fs"
	"net/http"
	"path"
	"strings"

	"github.com/gin-gonic/gin"
)

//go:embed webdist
var webDist embed.FS

// registerWebStatic 把前端静态资源挂到 NoRoute 上。
// Gin 的 NoRoute 处理器按注册顺序执行；系统短链代理只处理 /api/ 开头的
// 路径，因此静态处理器先行、其余交还给 proxy，既不遮挡业务路由，
// 也不破坏原有的短链代理行为。
//
// 坑：http.FileServer 对以 /index.html 结尾的请求会 301 规范化到目录
// （serveFile 的 localRedirect），若 SPA 入口走 FileServer 会形成
// / → /index.html → / 的死循环（浏览器报 ERR_TOO_MANY_REDIRECTS，
// 且 301 会被浏览器缓存）。因此 index.html 一律用 c.Data 直接写回。
func registerWebStatic(r *gin.Engine, proxy gin.HandlerFunc) {
	dist, err := fs.Sub(webDist, "webdist")
	if err != nil {
		r.NoRoute(proxy)
		return
	}
	indexHTML, err := fs.ReadFile(dist, "index.html")
	if err != nil {
		r.NoRoute(proxy)
		return
	}
	fileServer := http.FileServer(http.FS(dist))
	serveIndex := func(c *gin.Context) {
		c.Data(http.StatusOK, "text/html; charset=utf-8", indexHTML)
	}
	r.NoRoute(func(c *gin.Context) {
		p := path.Clean(c.Request.URL.Path)
		// /api 留给业务路由与短链代理。
		if p == "/api" || strings.HasPrefix(p, "/api/") {
			proxy(c)
			return
		}
		// SPA 入口直接写回，不经过 FileServer（避开 /index.html 301 坑）。
		if p == "/" || p == "/index.html" {
			serveIndex(c)
			return
		}
		// 精确命中的静态资源直接 serve（排除目录，避免目录列表泄露）。
		if name := strings.TrimPrefix(p, "/"); name != "" {
			if fi, err := fs.Stat(dist, name); err == nil && !fi.IsDir() {
				fileServer.ServeHTTP(c.Writer, c.Request)
				return
			}
		}
		// SPA fallback：无扩展名的路径一律回 index.html；
		// 带扩展名但不存在的资源走原 404 信封。
		if path.Ext(p) == "" {
			serveIndex(c)
			return
		}
		proxy(c)
	})
}
