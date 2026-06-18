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
