// 生成影策托盘图标：把 web/public/logo.svg 的几何造型（64 网格三笔笔画）
// 渲染成 256x256 深色圆角底 ICO（PNG 内嵌，Vista+ 托盘可直接用）。
// 仅标准库，可在 CI 上 go run 单文件执行，无需外部工具。
// 用法：go run main.go -out trayicon.ico
package main

import (
	"bytes"
	"encoding/binary"
	"flag"
	"image"
	"image/color"
	"image/draw"
	"image/png"
	"os"
)

const size = 256

var (
	bgColor = color.RGBA{0x23, 0x27, 0x3d, 0xff} // 深蓝灰底
	fgColor = color.RGBA{0xff, 0xff, 0xff, 0xff} // 白色笔画
)

// logo 笔画：由 SVG path 分解出的轴对齐矩形（64 网格坐标）。
var strokes = [][4]float64{
	// 笔画1 M6 8H36V16H14V36H28V44H6V8Z
	{6, 8, 36, 16}, {6, 16, 14, 44}, {14, 36, 28, 44},
	// 笔画2 M58 20H36V28H50V48H28V56H58V20Z
	{36, 20, 58, 28}, {50, 28, 58, 56}, {28, 48, 50, 56},
	// 笔画3 M24 27H40V37H24V27Z
	{24, 27, 40, 37},
}

func inRoundedRect(x, y, w, h, r int) bool {
	// 角落圆心钳制判断
	cx := x
	if cx < r {
		cx = r
	} else if cx > w-1-r {
		cx = w - 1 - r
	}
	cy := y
	if cy < r {
		cy = r
	} else if cy > h-1-r {
		cy = h - 1 - r
	}
	dx, dy := x-cx, y-cy
	return dx*dx+dy*dy <= r*r
}

func main() {
	out := flag.String("out", "trayicon.ico", "输出 ICO 路径")
	flag.Parse()

	img := image.NewRGBA(image.Rect(0, 0, size, size))
	// 透明底 + 深色圆角矩形
	for y := 0; y < size; y++ {
		for x := 0; x < size; x++ {
			if inRoundedRect(x, y, size, size, 52) {
				img.Set(x, y, bgColor)
			}
		}
	}
	// 白色笔画（64 网格 x4）
	k := float64(size) / 64
	for _, s := range strokes {
		r := image.Rect(int(s[0]*k), int(s[1]*k), int(s[2]*k), int(s[3]*k))
		draw.Draw(img, r, &image.Uniform{fgColor}, image.Point{}, draw.Src)
	}

	var pngBuf bytes.Buffer
	if err := png.Encode(&pngBuf, img); err != nil {
		panic(err)
	}
	pngData := pngBuf.Bytes()

	// ICO：ICONDIR + ICONDIRENTRY + PNG 数据（宽高写 0 表示 256）
	ico := new(bytes.Buffer)
	binary.Write(ico, binary.LittleEndian, uint16(0))  // reserved
	binary.Write(ico, binary.LittleEndian, uint16(1))  // type: icon
	binary.Write(ico, binary.LittleEndian, uint16(1))  // count
	ico.WriteByte(0)                                   // width (0 = 256)
	ico.WriteByte(0)                                   // height (0 = 256)
	ico.WriteByte(0)                                   // color count
	ico.WriteByte(0)                                   // reserved
	binary.Write(ico, binary.LittleEndian, uint16(1))  // planes
	binary.Write(ico, binary.LittleEndian, uint16(32)) // bit count
	binary.Write(ico, binary.LittleEndian, uint32(len(pngData)))
	binary.Write(ico, binary.LittleEndian, uint32(6+16)) // offset
	ico.Write(pngData)

	if err := os.WriteFile(*out, ico.Bytes(), 0o644); err != nil {
		panic(err)
	}
}
