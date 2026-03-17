"""Tests for src/sheets_utils.py"""

import pytest
from unittest.mock import MagicMock, patch
from src.sheets_utils import (
    parse_spreadsheet_url,
    resolve_sheet_name,
    read_column,
    write_cell,
)


class TestParseSpreadsheetUrl:
    def test_hash_gid(self):
        url = "https://docs.google.com/spreadsheets/d/1ABC123/edit#gid=456"
        sid, gid = parse_spreadsheet_url(url)
        assert sid == "1ABC123"
        assert gid == "456"

    def test_query_gid(self):
        url = "https://docs.google.com/spreadsheets/d/1DEF456/edit?gid=789"
        sid, gid = parse_spreadsheet_url(url)
        assert sid == "1DEF456"
        assert gid == "789"

    def test_both_gid(self):
        url = "https://docs.google.com/spreadsheets/d/1XtQw_lTdfqsv7XKrQOTQch4k1rCt7sT1AdlHKDwx5Hg/edit?gid=1066151357#gid=1066151357"
        sid, gid = parse_spreadsheet_url(url)
        assert sid == "1XtQw_lTdfqsv7XKrQOTQch4k1rCt7sT1AdlHKDwx5Hg"
        assert gid == "1066151357"

    def test_no_gid_defaults_to_zero(self):
        url = "https://docs.google.com/spreadsheets/d/1ABC123/edit"
        sid, gid = parse_spreadsheet_url(url)
        assert sid == "1ABC123"
        assert gid == "0"

    def test_invalid_url(self):
        with pytest.raises(ValueError, match="Cannot extract spreadsheet ID"):
            parse_spreadsheet_url("https://example.com/not-a-sheet")


class TestResolveSheetName:
    def test_matching_gid(self):
        service = MagicMock()
        service.spreadsheets().get().execute.return_value = {
            "sheets": [
                {"properties": {"sheetId": 0, "title": "Sheet1"}},
                {"properties": {"sheetId": 1066151357, "title": "Responses"}},
            ]
        }
        result = resolve_sheet_name(service, "spreadsheet_id", "1066151357")
        assert result == "Responses"

    def test_gid_not_found(self):
        service = MagicMock()
        service.spreadsheets().get().execute.return_value = {
            "sheets": [{"properties": {"sheetId": 0, "title": "Sheet1"}}]
        }
        with pytest.raises(ValueError, match="No sheet found with gid=999"):
            resolve_sheet_name(service, "spreadsheet_id", "999")


class TestReadColumn:
    def test_skips_header(self):
        service = MagicMock()
        service.spreadsheets().values().get().execute.return_value = {
            "values": [
                ["Video Link"],       # row 1 = header, skipped
                ["https://drive.google.com/file/d/abc"],  # row 2
                ["https://youtu.be/xyz"],                 # row 3
            ]
        }
        rows = read_column(service, "sid", "Responses", "Y")
        assert len(rows) == 2
        assert rows[0] == {"row": 2, "value": "https://drive.google.com/file/d/abc"}
        assert rows[1] == {"row": 3, "value": "https://youtu.be/xyz"}

    def test_empty_cells_included(self):
        service = MagicMock()
        service.spreadsheets().values().get().execute.return_value = {
            "values": [
                ["Header"],
                ["value"],
                [],          # empty row
            ]
        }
        rows = read_column(service, "sid", "Sheet1", "Z")
        assert rows[1] == {"row": 3, "value": ""}

    def test_empty_column(self):
        service = MagicMock()
        service.spreadsheets().values().get().execute.return_value = {"values": []}
        rows = read_column(service, "sid", "Sheet1", "Y")
        assert rows == []


class TestWriteCell:
    def test_calls_update_with_correct_range(self):
        service = MagicMock()
        write_cell(service, "sid123", "Responses", 5, "Z", "7.05")
        call_kwargs = service.spreadsheets().values().update.call_args
        assert call_kwargs.kwargs["range"] == "Responses!Z5"
        assert call_kwargs.kwargs["valueInputOption"] == "RAW"
        assert call_kwargs.kwargs["body"] == {"values": [["7.05"]]}
