# Timesheet Overlap Validator

A local FastAPI service that checks a proposed timesheet entry against existing
S/4HANA records and uses the Anthropic API (`claude-sonnet-4-6`) to detect
overlaps. Everything runs on your local machine — no Azure, Docker, or cloud
account required.

## Quick start

```bash
# 1. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate          # Mac/Linux
# venv\Scripts\activate           # Windows (Command Prompt)
# .\venv\Scripts\Activate.ps1     # Windows (PowerShell)

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure credentials
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

Response:

```json
{
  "hasOverlap": false,
  "conflicts":  [],
  "message":    "No conflicts found. Safe to post."
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
| Anthropic `AuthenticationError` | `ANTHROPIC_API_KEY` in `.env` is wrong or missing. |
| S/4HANA `401 Unauthorized` | `S4_USER` or `S4_PASS` in `.env` is incorrect. |
| S/4HANA `403 CSRF token validation failed` | Add the CSRF pre-request script (see Postman collection). |
| `json.JSONDecodeError` in terminal | Claude returned markdown instead of pure JSON. Retry once. |
| `hasOverlap` always false | Existing records have no `YY1_StartTime_TIM` value. |
