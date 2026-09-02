"""Ghi ban dang choi len Google Sheet.

SQLite la nguon su that duy nhat: moi lan /export bot ghi de toan bo tab, nen chay
bao nhieu lan cung ra ket qua giong nhau va khong bao gio trung dong.
gspread duoc import muon de bot van chay binh thuong khi chua setup Service Account.
"""

import json
import re
from datetime import datetime
from pathlib import Path

_KEY_IN_URL = re.compile(r"/spreadsheets/d/([A-Za-z0-9_-]+)")
_BARE_KEY = re.compile(r"^[A-Za-z0-9_-]{20,}$")

_BANKER_BG = {"red": 1.0, "green": 0.90, "blue": 0.60}
_HEADER_BG = {"red": 0.85, "green": 0.89, "blue": 0.95}


class SheetError(Exception):
    """Loi hien thi thang cho user."""


class SheetPermissionError(SheetError):
    pass


def extract_key(url: str) -> str:
    url = (url or "").strip()
    found = _KEY_IN_URL.search(url)
    if found:
        return found.group(1)
    if _BARE_KEY.match(url):
        return url
    raise SheetError(
        "Link Google Sheet không hợp lệ. Dán cả link dạng:\n"
        "https://docs.google.com/spreadsheets/d/<id>/edit"
    )


class SheetExporter:
    def __init__(self, sa_json_path: str | Path, tab_name: str):
        self.sa_json_path = Path(sa_json_path)
        self.tab_name = tab_name
        self._client = None

    @property
    def service_account_email(self) -> str:
        try:
            return json.loads(self.sa_json_path.read_text()).get("client_email", "?")
        except (OSError, ValueError):
            return "?"

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not self.sa_json_path.exists():
            raise SheetError(
                f"Chưa có file Service Account: {self.sa_json_path}\n"
                "Tạo Service Account trên Google Cloud, tải file JSON key về và trỏ "
                "GOOGLE_SA_JSON trong .env vào file đó."
            )
        try:
            import gspread
        except ImportError as exc:
            raise SheetError("Chưa cài gspread. Chạy: pip install -r requirements.txt") from exc
        self._client = gspread.service_account(filename=str(self.sa_json_path))
        return self._client

    # Ghi de tab, tra ve link tro thang toi tab da ghi.
    def export(self, sheet_url: str, title: str, header: list[str], rows: list[list],
               totals_row: list, banker_cells: list[tuple[int, int]]) -> str:
        client = self._get_client()
        key = extract_key(sheet_url)

        try:
            spreadsheet = client.open_by_key(key)
        except Exception as exc:
            raise self._translate(exc, key) from exc

        try:
            worksheet = spreadsheet.worksheet(self.tab_name)
        except Exception:
            worksheet = spreadsheet.add_worksheet(
                title=self.tab_name, rows=max(len(rows) + 20, 100), cols=max(len(header) + 4, 12)
            )

        values = [[title], header, *rows, totals_row]
        try:
            worksheet.clear()
            worksheet.update(values=values, range_name="A1")
            spreadsheet.batch_update(
                {"requests": self._format_requests(worksheet.id, header, rows, banker_cells)}
            )
        except Exception as exc:
            raise self._translate(exc, key) from exc

        return f"https://docs.google.com/spreadsheets/d/{key}/edit#gid={worksheet.id}"

    # Dong 1 = tieu de ban, dong 2 = header, dong cuoi = TONG; cell chuong duoc to mau.
    def _format_requests(self, sheet_id: int, header: list[str], rows: list[list],
                         banker_cells: list[tuple[int, int]]) -> list[dict]:
        total_row_idx = len(rows) + 2
        wide = {
            "sheetId": sheet_id,
            "startRowIndex": 0,
            "endRowIndex": total_row_idx + 5,
            "startColumnIndex": 0,
            "endColumnIndex": len(header) + 2,
        }
        requests: list[dict] = [
            {
                "repeatCell": {
                    "range": wide,
                    "cell": {"userEnteredFormat": {}},
                    "fields": "userEnteredFormat",
                }
            },
            {
                "repeatCell": {
                    "range": {**wide, "startRowIndex": 0, "endRowIndex": 1},
                    "cell": {"userEnteredFormat": {"textFormat": {"bold": True, "fontSize": 12}}},
                    "fields": "userEnteredFormat(textFormat)",
                }
            },
            {
                "repeatCell": {
                    "range": {**wide, "startRowIndex": 1, "endRowIndex": 2},
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"bold": True},
                            "backgroundColor": _HEADER_BG,
                            "horizontalAlignment": "CENTER",
                        }
                    },
                    "fields": "userEnteredFormat(textFormat,backgroundColor,horizontalAlignment)",
                }
            },
            {
                "repeatCell": {
                    "range": {
                        **wide,
                        "startRowIndex": total_row_idx,
                        "endRowIndex": total_row_idx + 1,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"bold": True},
                            "backgroundColor": _HEADER_BG,
                        }
                    },
                    "fields": "userEnteredFormat(textFormat,backgroundColor)",
                }
            },
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": sheet_id,
                        "gridProperties": {"frozenRowCount": 2, "frozenColumnCount": 1},
                    },
                    "fields": "gridProperties(frozenRowCount,frozenColumnCount)",
                }
            },
        ]
        for row_idx, col_idx in banker_cells:
            requests.append(
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": row_idx,
                            "endRowIndex": row_idx + 1,
                            "startColumnIndex": col_idx,
                            "endColumnIndex": col_idx + 1,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": _BANKER_BG,
                                "textFormat": {"bold": True},
                            }
                        },
                        "fields": "userEnteredFormat(backgroundColor,textFormat)",
                    }
                }
            )
        return requests

    # Doi loi Google thanh huong dan user tu xu ly duoc; 403/404 gan nhu luon la chua Share sheet.
    def _translate(self, exc: Exception, key: str) -> SheetError:
        status, message = _error_details(exc)
        email = self.service_account_email

        if "SERVICE_DISABLED" in message or "has not been used in project" in message:
            return SheetError(
                "Google Sheets API chưa được bật cho project của Service Account.\n"
                "Vào Google Cloud Console -> APIs & Services -> bật 'Google Sheets API' "
                "và 'Google Drive API', đợi 1-2 phút rồi thử lại."
            )
        if status in (401, 403, 404):
            return SheetPermissionError(
                "Bot chưa có quyền ghi vào sheet này.\n\n"
                "Mở sheet -> Share -> dán email dưới đây, chọn quyền Editor:\n"
                f"{email}\n\n"
                f"Sheet: https://docs.google.com/spreadsheets/d/{key}/edit\n"
                "Xong thì gõ export lại."
            )
        return SheetError(f"Lỗi khi ghi Google Sheet: {message[:300]}")


def _error_details(exc: Exception) -> tuple[int | None, str]:
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    message = str(exc)
    if response is not None:
        try:
            body = response.json()
            status = body.get("error", {}).get("code", status)
            message = body.get("error", {}).get("message", message)
        except ValueError:
            message = getattr(response, "text", message) or message
    if status is None and exc.__class__.__name__ == "SpreadsheetNotFound":
        status = 404
    return status, message


# Dung du lieu bang tu cac van dang hoat dong cua 1 ban.
def build_table(seats, rounds, totals, game_type: str = "3cay") -> tuple[str, list[str], list[list], list, list]:
    header = ["Giờ", *[p.name for p in seats]]
    rows: list[list] = []
    banker_cells: list[tuple[int, int]] = []

    for offset, rnd in enumerate(rounds):
        try:
            hhmm = datetime.fromisoformat(rnd.created_at).strftime("%H:%M")
        except ValueError:
            hhmm = ""
        cells = [rnd.scores.get(p.id, "") for p in seats]
        rows.append([hhmm, *cells])
        for seat_idx, player in enumerate(seats):
            if player.id == rnd.banker_id:
                banker_cells.append((offset + 2, seat_idx + 1))

    totals_row = ["TỔNG", *[totals.get(p.id, 0) for p in seats]]
    started = rounds[0].created_at[:10] if rounds else datetime.now().strftime("%Y-%m-%d")
    game_name = "Sâm" if game_type == "sam" else "3 cây"
    title = f"Bàn {game_name} ngày {started} - {len(rounds)} ván"
    return title, header, rows, totals_row, banker_cells
