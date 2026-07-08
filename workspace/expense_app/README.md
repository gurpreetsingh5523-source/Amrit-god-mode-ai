# 💰 Amrit Expense Tracker

Full-stack expense tracker built autonomously by Amrit God Mode AI.

## Files
- `api.py` — FastAPI + SQLite backend (POST/GET/summary/DELETE expenses)
- `index.html` — dark dashboard: add form, table, category bar chart (Chart.js)
- `test_api.py` — pytest suite (4 tests, all passing)

## Run
```bash
pip install fastapi uvicorn
python -m uvicorn api:app --reload     # API at http://localhost:8000
open index.html                         # dashboard (point it at the API)
pytest test_api.py                       # run tests
```
