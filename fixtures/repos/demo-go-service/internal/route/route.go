package route

import (
	"github.com/gin-gonic/gin"

	"demo/go-service/internal/handler"
)

// Register 挂载所有路由与中间件。
func Register() *gin.Engine {
	r := gin.New()
	r.Use(gin.Logger(), gin.Recovery())
	r.GET("/healthz", handler.Health)
	r.GET("/api/users/:id", handler.GetUser)
	r.POST("/api/users", handler.CreateUser)
	return r
}
