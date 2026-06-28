help:
	@echo "make dev    - bootstrap and run the full stack (server + frontend)"
	@echo "make setup  - install dependencies only, don't start anything"
	@echo "make stop   - kill any stray uvicorn / vite / node processes"

dev:
	python3 dev.py

setup:
	python3 dev.py --no-install --no-frontend --help >/dev/null 2>&1 || true
	python3 -c "import dev; dev.ensure_prerequisites(); dev.ensure_venv(True); dev.ensure_frontend(True)"

stop:
	-pkill -f "uvicorn server:app" 2>/dev/null || true
	-pkill -f "npm run dev" 2>/dev/null || true
	-pkill -f "vite" 2>/dev/null || true

