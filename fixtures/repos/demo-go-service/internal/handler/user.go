package handler

import (
	"net/http"

	"github.com/gin-gonic/gin"
)

func Health(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{"ok": true})
}

func GetUser(c *gin.Context) {
	id := c.Param("id")
	// TODO: 接入真实 repository 层
	c.JSON(http.StatusOK, gin.H{"id": id, "name": "demo"})
}

func CreateUser(c *gin.Context) {
	c.JSON(http.StatusCreated, gin.H{"created": true})
}
