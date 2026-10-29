package main

import (
	"log"
	"net/http"

	"demo/go-service/internal/route"
)

func main() {
	r := route.Register()
	addr := ":8080"
	log.Printf("listening on %s", addr)
	if err := http.ListenAndServe(addr, r); err != nil {
		log.Fatal(err)
	}
}
