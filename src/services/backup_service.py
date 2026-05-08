import csv
import io
import logging
import zipfile
from datetime import datetime

from services.cloudflare_service import CloudflareR2Service
from services.sheets_service import SheetsService

logger = logging.getLogger(__name__)


class BackupService:
    def __init__(self, sheets_service: SheetsService, cloudflare_service: CloudflareR2Service) -> None:
        self.sheets = sheets_service
        self.r2 = cloudflare_service

    async def run_daily_backup(self) -> str | None:
        """Backs up all Google Sheets to a ZIP file on Cloudflare R2."""
        try:
            logger.info("Starting daily cloud backup...")
            sheet_names = ["Trips", "Master_Vehicles", "Master_Drivers", "Attendance", "Daily_Summary"]

            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zip_file:
                for name in sheet_names:
                    records = self.sheets.get_records_safe(name)
                    if not records:
                        continue

                    # Convert records (list of dicts) to CSV
                    csv_buffer = io.StringIO()
                    writer = csv.DictWriter(csv_buffer, fieldnames=records[0].keys())
                    writer.writeheader()
                    writer.writerows(records)

                    zip_file.writestr(f"{name}.csv", csv_buffer.getvalue())

            # Upload to R2
            date_str = datetime.now().strftime("%Y-%m-%d")
            key = f"backups/{date_str}_fleet_backup.zip"

            zip_buffer.seek(0)
            self.r2.s3_client.put_object(
                Bucket=self.r2.bucket_name, Key=key, Body=zip_buffer.getvalue(), ContentType="application/zip"
            )

            logger.info(f"✅ Daily backup completed: {key}")
            return key
        except Exception as e:
            logger.error(f"❌ Backup failed: {e}")
            return None
