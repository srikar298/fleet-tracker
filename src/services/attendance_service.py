from datetime import datetime
from typing import Any

from services.sheets_service import SheetsService


class AttendanceService:
    def __init__(self, sheets_service: SheetsService) -> None:
        self.sheets = sheets_service

    def log_activity(self, driver_id: str | int, vendor_id: str) -> None:
        """Logs the first check-in or updates the last activity for a driver"""
        today = datetime.now().strftime("%Y-%m-%d")
        now_time = datetime.now().strftime("%H:%M:%S")

        sheet = self.sheets.get_sheet("Attendance")
        if not sheet:
            return

        records = sheet.get_all_records()
        for i, record in enumerate(records, start=2):
            if str(record.get("DriverID")) == str(driver_id) and record.get("Date") == today:
                sheet.update_cell(i, 5, now_time)
                return

        sheet.append_row([today, driver_id, vendor_id, now_time, now_time, "Present", "", ""])

    def get_daily_target(self, driver_id: str | int) -> dict[str, Any] | None:
        today = datetime.now().strftime("%Y-%m-%d")
        sheet = self.sheets.get_sheet("Attendance")
        if not sheet:
            return None
        for record in sheet.get_all_records():
            if str(record.get("DriverID")) == str(driver_id) and record.get("Date") == today:
                t_type = record.get("Target_Type")
                if t_type:
                    try:
                        val = float(record.get("Target_Value", 0))
                    except (ValueError, TypeError):
                        val = 0.0
                    return {
                        "type": t_type,
                        "value": val,
                    }
                return None
        return None

    def set_daily_target(self, driver_id: str | int, vendor_id: str, t_type: str, t_value: float) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        now_time = datetime.now().strftime("%H:%M:%S")
        sheet = self.sheets.get_sheet("Attendance")
        if not sheet:
            return

        records = sheet.get_all_records()
        for i, record in enumerate(records, start=2):
            if str(record.get("DriverID")) == str(driver_id) and record.get("Date") == today:
                sheet.update_cell(i, 7, t_type)
                sheet.update_cell(i, 8, t_value)
                return

        # If no check-in row exists, create it
        sheet.append_row(
            [
                today,
                driver_id,
                vendor_id,
                now_time,
                now_time,
                "Present",
                t_type,
                t_value,
            ]
        )
