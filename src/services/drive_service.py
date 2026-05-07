import io
import os
from datetime import datetime

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload


class DriveService:
    def __init__(self):
        self.folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
        self.credentials_file = os.getenv("SERVICE_ACCOUNT_FILE", "credentials.json")

        # Scopes for Drive API
        self.scopes = ["https://www.googleapis.com/auth/drive.file"]
        
        json_content = os.getenv("GOOGLE_CREDENTIALS_JSON")
        if json_content:
            import json
            info = json.loads(json_content)
            self.creds = Credentials.from_service_account_info(
                info, scopes=self.scopes
            )
        else:
            self.creds = Credentials.from_service_account_file(
                self.credentials_file, scopes=self.scopes
            )
        self.service = build("drive", "v3", credentials=self.creds)

        # Cache for subfolders to avoid redundant API calls
        self._folder_cache = {}

    def _get_or_create_subfolder(self, name, parent_id):
        """Finds or creates a subfolder within a parent folder."""
        cache_key = f"{parent_id}_{name}"
        if cache_key in self._folder_cache:
            return self._folder_cache[cache_key]

        query = (
            f"name = '{name}' and '{parent_id}' in parents and "
            f"mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        )
        results = (
            self.service.files().list(q=query, fields="files(id, name)").execute()
        )
        files = results.get("files", [])

        if files:
            folder_id = files[0]["id"]
        else:
            file_metadata = {
                "name": name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [parent_id],
            }
            folder = (
                self.service.files()
                .create(body=file_metadata, fields="id")
                .execute()
            )
            folder_id = folder.get("id")

        self._folder_cache[cache_key] = folder_id
        return folder_id

    def upload_file(self, file_content, driver_name, trip_id, image_type):
        """Uploads a file to a structured cloud hierarchy on Google Drive."""
        try:
            date_str = datetime.now().strftime("%Y-%m-%d")
            safe_driver_name = "".join([c if c.isalnum() else "_" for c in driver_name])

            # Navigate/Create hierarchy: Root -> Date -> Driver -> TripID
            date_folder = self._get_or_create_subfolder(date_str, self.folder_id)
            driver_folder = self._get_or_create_subfolder(
                safe_driver_name, date_folder
            )
            trip_folder = self._get_or_create_subfolder(trip_id, driver_folder)

            filename = f"{image_type}.jpg"
            file_metadata = {"name": filename, "parents": [trip_folder]}

            fh = io.BytesIO(file_content)
            media = MediaIoBaseUpload(fh, mimetype="image/jpeg", resumable=True)

            file = (
                self.service.files()
                .create(body=file_metadata, media_body=media, fields="id, webViewLink")
                .execute()
            )

            # Make file viewable by anyone with the link (optional, depends on security needs)
            # For B2B transparency, we usually want the link to be accessible
            self.service.permissions().create(
                fileId=file.get("id"),
                body={"type": "anyone", "role": "viewer"},
            ).execute()

            return file.get("webViewLink")
        except Exception as e:
            print(f"Error uploading to Cloud Drive: {e}")
            return None

    def flag_trip_images(self, date_str, driver_name, trip_id):
        """Flags a trip by adding a 'FLAGGED' description to the folder."""
        # Note: In Drive API, we can't easily 'copy' a whole folder structure with one call
        # but we can rename or add a description for the auditor.
        try:
            date_folder = self._get_or_create_subfolder(date_str, self.folder_id)
            driver_folder = self._get_or_create_subfolder(
                "".join([c if c.isalnum() else "_" for c in driver_name]), date_folder
            )
            
            # Find the trip folder
            query = f"name = '{trip_id}' and '{driver_folder}' in parents and trashed = false"
            results = self.service.files().list(q=query, fields="files(id)").execute()
            files = results.get("files", [])
            
            if files:
                folder_id = files[0]["id"]
                self.service.files().update(
                    fileId=folder_id,
                    body={"description": "FLAGGED_FOR_REVIEW: Discrepancy detected"}
                ).execute()
                return True
        except Exception as e:
            print(f"Error flagging cloud folder: {e}")
        return False

    def save_kyc_document(self, file_content, driver_name):
        """Saves KYC to a dedicated 'Compliance' subfolder."""
        try:
            kyc_root = self._get_or_create_subfolder("03_Compliance_KYC", self.folder_id)
            safe_name = "".join([c if c.isalnum() else "_" for c in driver_name])
            filename = f"{safe_name}_License.jpg"
            
            file_metadata = {"name": filename, "parents": [kyc_root]}
            fh = io.BytesIO(file_content)
            media = MediaIoBaseUpload(fh, mimetype="image/jpeg")
            
            file = self.service.files().create(body=file_metadata, media_body=media, fields="webViewLink").execute()
            return file.get("webViewLink")
        except Exception:
            return None

    def save_fuel_receipt(self, file_content, driver_name, trip_id, vehicle_id, cost):
        """Saves fuel receipt both in trip folder and financial reconciliation folder."""
        # 1. Standard upload
        web_link = self.upload_file(file_content, driver_name, trip_id, "fuel_receipt")
        
        # 2. Duplicate to Finance folder for accounting
        try:
            finance_root = self._get_or_create_subfolder("01_Financial_Reconciliation", self.folder_id)
            month_str = datetime.now().strftime("%Y-%m")
            month_folder = self._get_or_create_subfolder(month_str, finance_root)
            
            date_str = datetime.now().strftime("%Y-%m-%d")
            filename = f"{date_str}_{vehicle_id}_Rs{cost}.jpg"
            
            file_metadata = {"name": filename, "parents": [month_folder]}
            fh = io.BytesIO(file_content)
            media = MediaIoBaseUpload(fh, mimetype="image/jpeg")
            self.service.files().create(body=file_metadata, media_body=media).execute()
        except Exception:
            pass
            
        return web_link

    def save_expense_receipt(self, file_content, driver_name, vehicle_id, expense_amount):
        """Saves general expenses to dedicated folder."""
        try:
            expense_root = self._get_or_create_subfolder("02_Expense_Claims", self.folder_id)
            date_str = datetime.now().strftime("%Y-%m-%d")
            safe_name = "".join([c if c.isalnum() else "_" for c in driver_name])
            filename = f"{date_str}_{safe_name}_{vehicle_id}_Rs{expense_amount}.jpg"
            
            file_metadata = {"name": filename, "parents": [expense_root]}
            fh = io.BytesIO(file_content)
            media = MediaIoBaseUpload(fh, mimetype="image/jpeg")
            file = self.service.files().create(body=file_metadata, media_body=media, fields="webViewLink").execute()
            return file.get("webViewLink")
        except Exception:
            return None

    def save_incident_report(self, file_content, driver_name, vehicle_id):
        """Saves incident reports to dedicated folder."""
        try:
            incident_root = self._get_or_create_subfolder("04_Incident_Reports", self.folder_id)
            date_str = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            filename = f"{date_str}_{vehicle_id}_Damage.jpg"
            
            file_metadata = {"name": filename, "parents": [incident_root]}
            fh = io.BytesIO(file_content)
            media = MediaIoBaseUpload(fh, mimetype="image/jpeg")
            file = self.service.files().create(body=file_metadata, media_body=media, fields="webViewLink").execute()
            return file.get("webViewLink")
        except Exception:
            return None
