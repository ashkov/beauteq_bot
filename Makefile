all: build down up

down:
	docker compose down
up:
	docker compose up -d
build:
	docker compose build