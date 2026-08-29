.PHONY: bootstrap test build

bootstrap:
	python scripts/bootstrap_demo.py

test:
	backend/.venv/bin/python -m pytest backend/tests -q

build:
	cd frontend && npm run build

