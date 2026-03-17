"""Google Sheets API utilities."""

import re

from google.oauth2 import service_account
from googleapiclient.discovery import build


def get_sheets_service(credentials_file="ds-dream11-0eb59d82137f.json"):
    """Build authenticated Sheets API v4 service."""
    creds = service_account.Credentials.from_service_account_file(
        credentials_file,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    return build("sheets", "v4", credentials=creds)


def parse_spreadsheet_url(url: str) -> tuple[str, str]:
    """Extract (spreadsheet_id, gid) from a Google Sheets URL.

    Handles patterns like:
      spreadsheets/d/{ID}/edit?gid={GID}
      spreadsheets/d/{ID}/edit#gid={GID}
    """
    id_match = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url)
    if not id_match:
        raise ValueError(f"Cannot extract spreadsheet ID from URL: {url}")
    spreadsheet_id = id_match.group(1)

    gid_match = re.search(r"[#?&]gid=(\d+)", url)
    gid = gid_match.group(1) if gid_match else "0"

    return spreadsheet_id, gid


def resolve_sheet_name(service, spreadsheet_id: str, gid: str) -> str:
    """Return the sheet title for the given gid."""
    spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    gid_int = int(gid)
    for sheet in spreadsheet.get("sheets", []):
        props = sheet.get("properties", {})
        if props.get("sheetId") == gid_int:
            return props["title"]
    raise ValueError(f"No sheet found with gid={gid} in spreadsheet {spreadsheet_id}")


def read_column(service, spreadsheet_id: str, sheet_name: str, col_letter: str) -> list[dict]:
    """Read all values in a column.

    Returns list of {"row": int, "value": str} (1-indexed, header row 1 skipped).
    """
    range_notation = f"{sheet_name}!{col_letter}:{col_letter}"
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=range_notation)
        .execute()
    )
    values = result.get("values", [])

    rows = []
    for i, row in enumerate(values):
        row_num = i + 1  # 1-indexed
        if row_num == 1:
            continue  # skip header
        value = row[0] if row else ""
        rows.append({"row": row_num, "value": value})
    return rows


def write_cell(
    service,
    spreadsheet_id: str,
    sheet_name: str,
    row: int,
    col_letter: str,
    value: str,
):
    """Write a value to a single cell."""
    cell_range = f"{sheet_name}!{col_letter}{row}"
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=cell_range,
        valueInputOption="RAW",
        body={"values": [[value]]},
    ).execute()
