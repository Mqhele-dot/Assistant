# Core Service (FastAPI)

Run locally:
```bash
cd services/core
pip install -r requirements.txt
uvicorn main:app --reload
```

Data is persisted in `services/core/data.db` (SQLite).

Fallback (no dependencies):
```bash
cd services/core
python run.py
```

Endpoints:
- `POST /chat`
- `POST /codex/run`
- `GET /projects` / `POST /projects`
- `GET /logs`
- `POST /permissions`
- `GET /skills`
- `POST /skills/enable`
- `GET /skills/{skill}/prompt`
- `GET /health`
