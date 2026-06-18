import httpx
import json
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from anthropic import Anthropic

# Load values from .env file
load_dotenv()

S4_BASE_URL   = os.getenv("S4_BASE_URL")
S4_USER       = os.getenv("S4_USER")
S4_PASS       = os.getenv("S4_PASS")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")

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
    result   = await ask_claude(existing, req.startTime, req.endTime)
    return result


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
        response = await client.get(
            url, params=params, auth=(S4_USER, S4_PASS)
        )
        response.raise_for_status()

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


# ── Ask Claude to detect overlaps ────────────────────────────────
async def ask_claude(
    existing_records: list,
    proposed_start:   str,
    proposed_end:     str
) -> dict:

    client = Anthropic(api_key=ANTHROPIC_KEY)

    prompt = f"""You are a timesheet overlap detector.
Times are in OData V2 format: PT08H00M00S means 8:00 AM.

Existing entries for this employee today:
{json.dumps(existing_records, indent=2)}

Proposed new entry:
Start: {proposed_start}
End:   {proposed_end}

Two intervals overlap if one starts before the other ends.
Respond ONLY in valid JSON — no markdown, no extra text:
{{
  \"hasOverlap\": true or false,
  \"conflicts\": [
    {{
      \"TimeSheetRecord\": \"record number\",
      \"existingStart\": \"HH:MM\",
      \"existingEnd\": \"HH:MM\",
      \"overlapPeriod\": \"HH:MM to HH:MM\"
    }}
  ],
  \"message\": \"plain English explanation\"
}}"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )

    return json.loads(response.content[0].text)
