import logging
import os

from services.attendance_service import AttendanceService
from services.drive_service import DriveService
from services.sheets_service import SheetsService

logger = logging.getLogger(__name__)


class BaseHandler:
    """Base class for all Telegram handlers, providing injected services."""

    def __init__(self, sheets: SheetsService, drive: DriveService, attendance: AttendanceService):
        self.sheets = sheets
        self.drive = drive
        self.attendance = attendance
        self.admin_ids = [int(i.strip()) for i in os.getenv("ADMIN_IDS", "").split(",") if i.strip()]

    def is_admin(self, user_id):
        return user_id in self.admin_ids
