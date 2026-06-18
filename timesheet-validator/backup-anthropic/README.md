# Backup — Anthropic API version

This folder preserves the **original** implementation that used the Anthropic
API (`claude-sonnet-4-6`) to detect timesheet overlaps, exactly as it was in the
first commit (`bafd4d8`), before it was replaced by the deterministic
pure-Python version in the parent folder.

It is kept here for reference only and is **not** used by the running service.

## Contents

| File | Notes |
|------|-------|
| `main.py` | FastAPI app where `ask_claude()` sends the records to Claude and parses the JSON reply. |
| `requirements.txt` | Includes the extra `anthropic` dependency. |
| `.env.example` | Includes the extra `ANTHROPIC_API_KEY` credential. |

## To run this version instead

Copy these three files over the ones in the parent `timesheet-validator/`
folder, then:

```bash
pip install -r requirements.txt        # installs the anthropic SDK
cp .env.example .env                   # add your ANTHROPIC_API_KEY
uvicorn main:app --reload --port 8000
```

The request/response shape is identical to the current version, so the same
Postman tests apply.
