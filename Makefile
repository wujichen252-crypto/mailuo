.PHONY: help up down dev seed eval test web build docker

help:
	@echo "make up      - docker compose 起服务（8080）"
	@echo "make dev     - 本机起后端（8000，前端用 web/dist）"
	@echo "make seed    - 导入种子库（离线 fixture）"
	@echo "make eval    - 跑评测（检索/引用/槽位）"
	@echo "make test    - 跑单测"
	@echo "make web     - 构建前端（需要 Node/pnpm）"

up:
	docker compose up -d --build

down:
	docker compose down

dev:
	python -m app.cli serve

seed:
	python -m app.cli seed

eval:
	python scripts/eval.py

test:
	python -m pytest -q

web:
	cd web && pnpm install && pnpm build

build: web
	docker build -t mailuo:local .
