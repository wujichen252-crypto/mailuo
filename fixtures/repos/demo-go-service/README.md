# demo-go-service

一个用于演示交接流程的极小 Go 服务：提供用户查询接口，带 Redis 缓存与中间件。

## 快速开始

```bash
cp .env.example .env
go run main.go
```

服务默认监听 `:8080`，健康检查 `GET /healthz`。

## 目录

```
internal/handler    HTTP 处理函数
internal/route      路由注册与中间件挂载
internal/cache      Redis 客户端封装
config              环境变量与常量
```
