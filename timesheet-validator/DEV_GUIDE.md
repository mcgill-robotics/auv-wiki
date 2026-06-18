# FastAPI Timesheet Validator — Local Development & Postman Testing Guide

**Pure-Python overlap detection (no AI provider required)**

| Property      | Value                                   |
|---------------|-----------------------------------------|
| Application   | Timesheet Overlap Validation Service    |
| Framework     | Python FastAPI                          |
| Overlap logic | Deterministic Python (interval compare) |
| Test tool     | Postman                                 |
| Date          | June 18, 2026                           |

> **Why this approach?** Detecting whether two time intervals overlap is a
> simple, exact calculation. The earlier version sent the records to the
> Anthropic API to decide — which added network latency, per-request cost,
> non-determinism, and a chance of `JSONDecodeError` when the model replied
> with markdown. This guide uses plain Python instead: it is instant, free,
> always correct, and works offline. An LLM only earns its place when the input
> is messy free text or the rules are genuinely fuzzy — neither is true here.

---

## Tools You Need

Before starting, make sure you have these four tools installed on your machine.

| Tool        | What It Does / Where to Get It |
|-------------|--------------------------------|
| Python 3.9+ | Runs your FastAPI app. Download from [python.org](https://www.python.org). Check version: `python --version` |
| VS Code     | Code editor for writing `main.py`. Download from [code.visualstudio.com](https://code.visualstudio.com). Any editor works. |
| Postman     | API testing tool for sending requests to your service. Download from [postman.com](https://www.postman.com). |
| Terminal    | Command line for running `pip` and `uvicorn`. Use Terminal (Mac), Command Prompt or PowerShell (Windows). |

You do **NOT** need Azure, Docker, an Anthropic account, or any cloud account
for this guide. Everything runs on your local machine.

---

## Step 1 — Create Your Project Folder

**Tool: Terminal** — Command Prompt (Windows) or Terminal (Mac/Linux)

Open your terminal and run these commands one at a time:

```bash
mkdir timesheet-validator
cd timesheet-validator
```

This creates a folder called `timesheet-validator` and moves you into it. All
your files will go here.

---

## Step 2 — Create a Virtual Environment

**Tool: Terminal** — Keeps this project's packages separate from other projects

A virtual environment is a clean Python sandbox just for this project.

**Mac / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows (Command Prompt):**
```bat
python -m venv venv
venv\Scripts\activate
```

**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Your terminal prompt should now show `(venv)` at the start. If you close the
terminal and come back later, run the activate command again before running
your app.

---

## Step 3 — Install Required Packages

**Tool: Terminal** — `pip` installs the Python packages your app needs

With the virtual environment active, run:

```bash
pip install fastapi uvicorn httpx python-dotenv
```

> Note: there is **no `anthropic` package** in this approach. That is the whole
> point — one fewer dependency and no API key to manage.

| Package        | Why You Need It |
|----------------|-----------------|
| `fastapi`      | The web framework that creates your API endpoint |
| `uvicorn`      | The server that runs your FastAPI app locally |
| `httpx`        | Makes HTTP calls to the S/4HANA OData API |
| `python-dotenv`| Reads your credentials from the `.env` file |

---

## Step 4 — Create the `.env` File

**Tool: VS Code or any text editor** — Stores your credentials outside your code

In your `timesheet-validator` folder, create a file called exactly `.env`
(note the leading dot). Paste the following and fill in your real values:

```bash
# S/4HANA connection
S4_BASE_URL=https://my423259-api.s4hana.cloud.sap
S4_USER=POSTMAN_USER
S4_PASS=your_communication_user_password
```

> There is **no `ANTHROPIC_API_KEY`** — the validator no longer calls any AI
> service. Never share `.env` or commit it to Git; add it to `.gitignore`.

---

## Step 5 — Create `main.py`

**Tool: VS Code** — This is the complete application code

In your `timesheet-validator` folder, create `main.py` and paste in the
complete code below. The overlap detection lives entirely in
`detect_overlaps()` — no external calls.

```python
import os
import re
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

# Load values from .env file
load_dotenv()

S4_BASE_URL = os.getenv("S4_BASE_URL")
S4_USER     = os.getenv("S4_USER")
S4_PASS     = os.getenv("S4_PASS")

app = FastAPI(title="Timesheet Overlap Validator")


# ── Request model ────────────────────────────────────────────────
class ValidateRequest(BaseModel):
    employeeId: str   # e.g. P000020
    date:       str   # e.g. 2026-06-17
    startTime:  str   # e.g. PT08H00M00S
    endTime:    str   # e.g. PT10H00M00S


# ── Main endpoint ────────────────────────────────────────────────
@app.post("/validate-overlap")
async def validate_overlap(req: ValidateRequest):
    existing = await fetch_s4_records(req.employeeId, req.date)
    return detect_overlaps(existing, req.startTime, req.endTime)


# ── Health check ─────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Fetch records from S/4HANA ───────────────────────────────────
async def fetch_s4_records(employee_id: str, date: str) -> list:
    url = (
        f"{S4_BASE_URL}/sap/opu/odata/sap/"
        "API_MANAGE_WORKFORCE_TIMESHEET/TimeSheetEntryCollection"
    )
    params = {
        "$filter": (
            f"PersonWorkAgreementExternalID eq '{employee_id}'"
            f" and TimeSheetDate eq datetime'{date}T00:00:00'"
        ),
        "$select": (
            "TimeSheetRecord,YY1_StartTime_TIM,"
            "YY1_EndTime_TIM,RecordedHours"
        ),
        "$format": "json"
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                url, params=params, auth=(S4_USER, S4_PASS)
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=f"S/4HANA request failed: {exc.response.text}"
            )
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Could not reach S/4HANA: {exc}"
            )

    records = response.json()["d"]["results"]
    return [
        {
            "TimeSheetRecord": r["TimeSheetRecord"],
            "startTime":       r["YY1_StartTime_TIM"],
            "endTime":         r["YY1_EndTime_TIM"]
        }
        for r in records
        if r.get("YY1_StartTime_TIM") and r.get("YY1_EndTime_TIM")
    ]


# ── Time helpers ─────────────────────────────────────────────────
_DURATION_RE = re.compile(
    r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$", re.IGNORECASE
)


def parse_odata_time(value: str) -> int:
    """Convert an OData V2 duration like 'PT08H30M00S' to minutes past midnight."""
    match = _DURATION_RE.match(value.strip())
    if not match:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid OData time format: '{value}'. Expected e.g. PT08H00M00S."
        )
    hours, minutes, _seconds = (int(g) if g else 0 for g in match.groups())
    return hours * 60 + minutes


def format_hhmm(minutes: int) -> str:
    """Render minutes-past-midnight as 'HH:MM'."""
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


# ── Detect overlaps (deterministic) ──────────────────────────────
def detect_overlaps(
    existing_records: list,
    proposed_start:   str,
    proposed_end:     str
) -> dict:
    """Compare the proposed entry against existing approved records.

    Two intervals overlap when one starts strictly before the other ends:
    existingStart < proposedEnd AND proposedStart < existingEnd.
    """
    p_start = parse_odata_time(proposed_start)
    p_end   = parse_odata_time(proposed_end)

    if p_end <= p_start:
        raise HTTPException(
            status_code=422,
            detail=(
                f"endTime ({format_hhmm(p_end)}) must be after "
                f"startTime ({format_hhmm(p_start)})."
            )
        )

    conflicts = []
    for record in existing_records:
        e_start = parse_odata_time(record["startTime"])
        e_end   = parse_odata_time(record["endTime"])

        # Overlap test
        if e_start < p_end and p_start < e_end:
            overlap_start = max(p_start, e_start)
            overlap_end   = min(p_end, e_end)
            conflicts.append({
                "TimeSheetRecord": record["TimeSheetRecord"],
                "existingStart":   format_hhmm(e_start),
                "existingEnd":     format_hhmm(e_end),
                "overlapPeriod":   (
                    f"{format_hhmm(overlap_start)} to {format_hhmm(overlap_end)}"
                ),
                "overlapMinutes":  overlap_end - overlap_start,
            })

    proposed_window = f"{format_hhmm(p_start)}-{format_hhmm(p_end)}"

    if not conflicts:
        return {
            "hasOverlap": False,
            "conflicts":  [],
            "message":    "No conflicts found. Safe to post.",
        }

    # Build a clear, human-readable explanation listing every conflict.
    details = "; ".join(
        f"record {c['TimeSheetRecord']} ({c['existingStart']}-{c['existingEnd']}, "
        f"overlapping {c['overlapPeriod']})"
        for c in conflicts
    )
    count = len(conflicts)
    noun  = "approved entry" if count == 1 else "approved entries"
    message = (
        f"Proposed time {proposed_window} overlaps {count} {noun}: {details}. "
        f"Adjust the start/end time to avoid these periods before posting."
    )

    return {
        "hasOverlap": True,
        "conflicts":  conflicts,
        "message":    message,
    }
```

### How the overlap logic works

1. **Parse** each `PTxxHxxMxxS` value into minutes past midnight
   (`PT08H30M00S` → `510`).
2. **Validate** the proposed window (`endTime` must be after `startTime`).
3. For each existing approved record, apply the interval test:
   `existingStart < proposedEnd AND proposedStart < existingEnd`.
4. For every match, record the exact overlap window
   (`max(starts)` → `min(ends)`) and its length in minutes.
5. **Build a clear message** that lists every conflicting record so the user
   knows exactly which approved times to avoid.

---

## Step 6 — Start the Server

**Tool: Terminal** — Uvicorn runs your FastAPI app on port 8000

With the virtual environment active, run:

```bash
uvicorn main:app --reload --port 8000
```

You should see:

```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

Your service is now live at <http://localhost:8000>. The `--reload` flag
restarts the server automatically whenever you save `main.py`.

Open the auto-generated API docs at <http://localhost:8000/docs>.

---

## Step 7 — Test With Postman

**Tool: Postman** — Send HTTP requests to your running FastAPI service

You will run three tests in order.

### Test 1 — Health Check

| Setting | Value |
|---------|-------|
| Method  | GET   |
| URL     | `http://localhost:8000/health` |

Click **Send**. Expected response:

```json
{ "status": "ok" }
```

### Test 2 — Validate No Overlap

| Setting       | Value |
|---------------|-------|
| Method        | POST  |
| URL           | `http://localhost:8000/validate-overlap` |
| Body type     | raw → JSON |

Body:

```json
{
  "employeeId": "P000020",
  "date":       "2026-06-17",
  "startTime":  "PT10H00M00S",
  "endTime":    "PT12H00M00S"
}
```

Expected response:

```json
{
  "hasOverlap": false,
  "conflicts":  [],
  "message":    "No conflicts found. Safe to post."
}
```

### Test 3 — Validate With Overlap

Same setup as Test 2. Use a time range that overlaps an existing approved record:

```json
{
  "employeeId": "P000020",
  "date":       "2026-06-17",
  "startTime":  "PT08H00M00S",
  "endTime":    "PT10H00M00S"
}
```

Expected response — note the `message` names the exact conflicting record and
overlap period:

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

If the proposed window spans several approved entries, every one of them is
listed in `conflicts` and named in `message`.

---

## Step 8 — POST Timesheet to S/4HANA (After Validation Passes)

**Tool: Postman** — Call the S/4HANA OData API directly

When the validator returns `"hasOverlap": false`, the external system posts the
timesheet to S/4HANA. This step is unchanged from the original approach.

### 8.1 CSRF Token Fetch (Pre-request Script)

SAP requires a CSRF token for all POST requests. Add this to the **Pre-request
Script** tab:

```javascript
pm.sendRequest({
    url: "https://my423259-api.s4hana.cloud.sap/sap/opu/odata/sap/"
         + "API_MANAGE_WORKFORCE_TIMESHEET/",
    method: "GET",
    header: {
        "x-csrf-token":  "fetch",
        "Authorization": "Basic " + btoa("POSTMAN_USER:your_password")
    }
}, function (err, res) {
    pm.request.headers.upsert({
        key:   "x-csrf-token",
        value: res.headers.get("x-csrf-token")
    });
});
```

### 8.2 Configure the POST Request

| Setting       | Value |
|---------------|-------|
| Method        | POST  |
| URL           | `https://my423259-api.s4hana.cloud.sap/sap/opu/odata/sap/API_MANAGE_WORKFORCE_TIMESHEET/TimeSheetEntryCollection` |
| Authorization | Basic Auth — Username `POSTMAN_USER`, Password `your_password` |
| Content-Type  | `application/json` |
| Accept        | `application/json` |

### 8.3 Request Body

```json
{
  "TimeSheetOperation":            "C",
  "PersonWorkAgreementExternalID": "P000020",
  "CompanyCode":                   "1090",
  "TimeSheetDate":                 "2026-06-17T00:00:00",
  "TimeSheetIsReleasedOnSave":      false,
  "TimeSheetIsExecutedInTestRun":   false,
  "TimeSheetDataFields": {
    "ControllingArea":             "A000",
    "SenderCostCenter":            "5101090",
    "ActivityType":                "T005",
    "WBSElement":                  "S.POCTST2.01.1.03",
    "RecordedHours":               "2.00",
    "RecordedQuantity":            "2.000",
    "HoursUnitOfMeasure":          "H",
    "SendingPubSecFunctionalArea": "YB10",
    "ReceiverPubSecFuncnlArea":    "YB99"
  },
  "YY1_StartTime_TIM": "PT10H00M00S",
  "YY1_EndTime_TIM":   "PT12H00M00S"
}
```

### 8.4 Verify Success

Look for **HTTP 201 Created**, then a non-empty `TimeSheetRecord` in the body:

```json
{ "d": { "TimeSheetRecord": "000000000404", "TimeSheetStatus": "30" } }
```

| `TimeSheetStatus` | Meaning |
|-------------------|---------|
| `30`              | Approved — entry created and auto-approved |
| `20`              | Pending approval — created, awaiting manager |
| empty string      | Not created — `TimeSheetIsExecutedInTestRun` is still `true` |

---

## Step 9 — Troubleshooting

| Problem | Fix |
|---------|-----|
| `uvicorn: command not found` | Virtual environment not active. Run `source venv/bin/activate` (Mac) or `venv\Scripts\activate` (Windows). |
| `ModuleNotFoundError: No module named 'fastapi'` | Run `pip install fastapi uvicorn httpx python-dotenv` in the active venv. |
| Could not load `.env` | The `.env` file must be in the same folder as `main.py`. |
| Postman: Connection refused | Uvicorn is not running. Start it with `uvicorn main:app --reload --port 8000`. |
| `422 Invalid OData time format` | A `startTime`/`endTime` is not in `PTxxHxxMxxS` form (e.g. `PT08H00M00S`). |
| `422 endTime must be after startTime` | The proposed window is zero-length or reversed. |
| S/4HANA `401 Unauthorized` | `S4_USER` or `S4_PASS` in `.env` is incorrect. |
| S/4HANA `403 CSRF token validation failed` | Add the CSRF Pre-request Script from Step 8.1. |
| `hasOverlap` always false | Existing records have no `YY1_StartTime_TIM` value, so they are skipped. |

> Note: the `json.JSONDecodeError` and Anthropic `AuthenticationError` problems
> from the AI-based guide **cannot happen here** — there is no model reply to
> parse and no API key to misconfigure.

---

## Quick Reference

### Commands Summary

```bash
# One-time setup (run once)
mkdir timesheet-validator && cd timesheet-validator
python -m venv venv
pip install fastapi uvicorn httpx python-dotenv

# Every time you work on the project
cd timesheet-validator
source venv/bin/activate          # Mac/Linux
venv\Scripts\activate             # Windows
uvicorn main:app --reload --port 8000

# Open in browser
# http://localhost:8000/health
# http://localhost:8000/docs
```

### OData Time Format

| Time     | OData Format |
|----------|--------------|
| 6:00 AM  | `PT06H00M00S` |
| 8:00 AM  | `PT08H00M00S` |
| 8:30 AM  | `PT08H30M00S` |
| 10:00 AM | `PT10H00M00S` |
| 12:00 PM | `PT12H00M00S` |
| 5:30 PM  | `PT17H30M00S` |

### File Structure

```
timesheet-validator/
├── venv/              (virtual environment — do not edit)
├── main.py            (your application code)
└── .env               (your credentials — never commit this)
```

### This approach vs. the Anthropic API approach

| | Pure Python (this guide) | Anthropic API (original) |
|---|---|---|
| Correctness | Always exact | Probabilistic |
| Latency | Microseconds | ~1–3 s per request |
| Cost | Free | Per-request API cost |
| Dependencies | 4 packages | 5 (adds `anthropic`) |
| Credentials | S/4HANA only | + `ANTHROPIC_API_KEY` |
| Offline / unit-testable | Yes | No |
| Best when | Inputs are clean & rules are exact | Inputs are messy free text / fuzzy rules |
