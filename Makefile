.PHONY: dev demo stop logs backend-dev frontend-dev setup

dev:
	docker compose up --build

dev-detached:
	docker compose up --build -d

stop:
	docker compose down

logs:
	docker compose logs -f

backend-dev:
	cd backend && uvicorn app:app --host 0.0.0.0 --port 8000 --reload

frontend-dev:
	cd frontend && npm run dev

setup:
	cp -n backend/.env.example backend/.env || true
	cp -n frontend/.env.example frontend/.env || true
	@echo "✅  .env files created – fill in your API keys"

demo:
	@echo "▶ Running prevention demo..."
	curl -s -X POST http://localhost:8000/api/demo/prevention | python3 -m json.tool
	@echo ""
	@echo "▶ Running fall demo..."
	curl -s -X POST http://localhost:8000/api/demo/fall | python3 -m json.tool

demo-prevention:
	curl -s -X POST http://localhost:8000/api/demo/prevention | python3 -m json.tool

demo-fall:
	curl -s -X POST http://localhost:8000/api/demo/fall | python3 -m json.tool

health:
	curl -s http://localhost:8000/health | python3 -m json.tool
