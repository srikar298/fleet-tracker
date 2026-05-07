import logging

from services.attendance_service import AttendanceService
from services.drive_service import DriveService
from services.sheets_service import SheetsService

logger = logging.getLogger(__name__)


class BaseHandler:
    """Base class for all Telegram handlers, providing injected services."""

    def __init__(
        self, sheets: SheetsService, drive: DriveService, attendance: AttendanceService
    ):
        self.sheets = sheets
        self.drive = drive
        self.attendance = attendance
