package config

import "os"

const DefaultPort = 8080

// Get 读取环境变量，缺省时回退默认值。
func Get(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

// 硬编码路径示例（用于演示 R1 规则命中）
const LogPath = "/home/jiangyh/app/logs/app.log"
