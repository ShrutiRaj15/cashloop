.PHONY: install seed train test simulation backend frontend all

install:
	pip install -r backend/requirements.txt
	cd frontend && npm install

seed:
	cd backend && python app/data/seed.py

train:
	cd backend && python -m app.ml.backtest

simulation:
	cd backend && python run_simulation.py

test:
	cd backend && python -m pytest tests -v

backend:
	cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

frontend:
	cd frontend && npm run dev

all: seed train simulation test
