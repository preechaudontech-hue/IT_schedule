"""Read schedule rows from a Google Sheet using a service account."""
from __future__ import annotations

import json
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


def _client(sa_json: str) -> gspread.Client:
    info = json.loads(sa_json)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)


def fetch_rows(sa_json: str, sheet_id: str, worksheet: str = "schedule") -> list[dict[str, Any]]:
    """Return worksheet rows as list of dicts keyed by the header row."""
    gc = _client(sa_json)
    ws = gc.open_by_key(sheet_id).worksheet(worksheet)
    return ws.get_all_records()
