# Timesheet Overlap Validator

A local FastAPI service that checks a proposed timesheet entry against existing
approved S/4HANA records and reports any overlaps. Overlap detection is pure,
deterministic Python — two intervals overlap when `existingStart < proposedEnd`
and `proposedStart < existingEnd` — so it is fast, free, and always correct (no
LLM needed). When a conflict is found, the response lists every approved entry
it clashes with and the exact overlapping period. Everything runs on your local
machine — no Azure, Docker, or cloud account required.

## Quick start

```bash
# 1. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate          # Mac/Linux
# venv\Scripts\activate           # Windows (Command Prompt)
# .\venv\Scripts\Activate.ps1     # Windows (PowerShell)

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure credentials (S/4HANA only — no API key required)
cp .env.example .env              # then edit .env with real values

# 4. Run the server
uvicorn main:app --reload --port 8000
```

Open <http://localhost:8000/docs> for the auto-generated API docs, or
<http://localhost:8000/health> for a quick health check.

## Endpoints

| Method | Path                | Description                              |
|--------|---------------------|------------------------------------------|
| GET    | `/health`           | Liveness check — returns `{"status":"ok"}` |
| POST   | `/validate-overlap` | Validates a proposed entry for overlaps  |

### `POST /validate-overlap`

Request body:

```json
{
  "employeeId": "P000020",
  "date":       "2026-06-17",
  "startTime":  "PT10H00M00S",
  "endTime":    "PT12H00M00S"
}
```

Response when there is no conflict:

```json
{
  "hasOverlap": false,
  "conflicts":  [],
  "message":    "No conflicts found. Safe to post."
}
```

Response when one or more approved entries overlap — `conflicts` lists each
clashing record and the `message` spells out exactly what to avoid:

```json
{
  "hasOverlap": true,
  "conflicts": [
    {
      "TimeSheetRecord": "000000000402",
      "existingStart":   "07:00",
      "existingEnd":     "09:00",
      "overlapPeriod":   "08:00 to 09:00",
      "overlapMinutes":  60
    }
  ],
  "message": "Proposed time 08:00-10:00 overlaps 1 approved entry: record 000000000402 (07:00-09:00, overlapping 08:00 to 09:00). Adjust the start/end time to avoid these periods before posting."
}
```

## Testing with Postman

Import `postman_collection.json` into Postman. It contains:

1. **Health Check** — `GET /health`
2. **Validate No Overlap** — `POST /validate-overlap`
3. **Validate With Overlap** — `POST /validate-overlap`
4. **POST Timesheet to S/4HANA** — direct OData call with a CSRF pre-request
   script (fill in your password first).

Set the collection variables `baseUrl`, `s4BaseUrl`, `s4User`, and `s4Pass`
under the collection's **Variables** tab.

## OData time format

| Time     | OData Format |
|----------|--------------|
| 6:00 AM  | `PT06H00M00S` |
| 8:00 AM  | `PT08H00M00S` |
| 8:30 AM  | `PT08H30M00S` |
| 10:00 AM | `PT10H00M00S` |
| 12:00 PM | `PT12H00M00S` |
| 5:30 PM  | `PT17H30M00S` |

## File structure

```
timesheet-validator/
├── main.py                   application code
├── requirements.txt          Python dependencies
├── .env.example              template for credentials
├── .env                      your credentials (never committed)
├── postman_collection.json   importable Postman tests
└── README.md                 this file
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `uvicorn: command not found` | Virtual environment is not active. Run the activate command. |
| `ModuleNotFoundError: No module named 'fastapi'` | Run `pip install -r requirements.txt` in the active venv. |
| Could not load `.env` | The `.env` file must be in the same folder as `main.py`. |
| Postman: Connection refused | Uvicorn is not running. Start it with `uvicorn main:app --reload --port 8000`. |
| S/4HANA `401 Unauthorized` | `S4_USER` or `S4_PASS` in `.env` is incorrect. |
| S/4HANA `403 CSRF token validation failed` | Add the CSRF pre-request script (see Postman collection). |
| `422 Invalid OData time format` | A `startTime`/`endTime` is not in `PTxxHxxMxxS` form (e.g. `PT08H00M00S`). |
| `hasOverlap` always false | Existing records have no `YY1_StartTime_TIM` value, so they are skipped. |
