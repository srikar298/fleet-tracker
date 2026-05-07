import os
import shutil
from datetime import datetime


class DriveService:
    def __init__(self):
        self.base_dir = os.path.join(os.getcwd(), "trip_images")
        self.flagged_dir = os.path.join(self.base_dir, "Flagged_Review")

        self.financial_dir = os.path.join(os.getcwd(), "01_Financial_Reconciliation")
        self.expense_dir = os.path.join(os.getcwd(), "02_Expense_Claims")
        self.kyc_dir = os.path.join(os.getcwd(), "03_Compliance_KYC")
        self.incident_dir = os.path.join(os.getcwd(), "04_Incident_Reports")
        self.archive_dir = os.path.join(os.getcwd(), "05_Archived_Data")

        for d in [
            self.base_dir,
            self.flagged_dir,
            self.financial_dir,
            self.expense_dir,
            self.kyc_dir,
            self.incident_dir,
            self.archive_dir,
        ]:
            os.makedirs(d, exist_ok=True)

    def upload_file(self, file_content, driver_name, trip_id, image_type):
        """Saves a file in a structured hierarchy for easy super admin auditing"""
        try:
            date_str = datetime.now().strftime("%Y-%m-%d")
            safe_driver_name = "".join([c if c.isalnum() else "_" for c in driver_name])

            # Path: trip_images/YYYY-MM-DD/DriverName/TripID/
            rel_dir = os.path.join(date_str, safe_driver_name, trip_id)
            abs_dir = os.path.join(self.base_dir, rel_dir)
            os.makedirs(abs_dir, exist_ok=True)

            filename = f"{image_type}.jpg"
            file_path = os.path.join(abs_dir, filename)

            with open(file_path, "wb") as f:
                f.write(file_content)

            # Return relative path for Google Sheet
            return os.path.join("trip_images", rel_dir, filename).replace("\\", "/")
        except Exception as e:
            print(f"Error saving image locally: {e}")
            return None

    def flag_trip_images(self, date_str, driver_name, trip_id):
        """Copies a trip's folder to the Flagged_Review folder for easy discrepancy audits"""  # noqa: E501
        safe_driver_name = "".join([c if c.isalnum() else "_" for c in driver_name])
        source_dir = os.path.join(self.base_dir, date_str, safe_driver_name, trip_id)
        target_dir = os.path.join(
            self.flagged_dir, f"{date_str}_{safe_driver_name}_{trip_id}"
        )

        if os.path.exists(source_dir):
            try:
                shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)
                return True
            except Exception as e:
                print(f"Error copying flagged images: {e}")
        return False

    def save_kyc_document(self, file_content, driver_name):
        safe_name = "".join([c if c.isalnum() else "_" for c in driver_name])
        filename = f"{safe_name}_License.jpg"
        filepath = os.path.join(self.kyc_dir, filename)
        with open(filepath, "wb") as f:
            f.write(file_content)
        return f"03_Compliance_KYC/{filename}"

    def save_fuel_receipt(self, file_content, driver_name, trip_id, vehicle_id, cost):
        # 1. Save standard trip structure
        rel_path = self.upload_file(file_content, driver_name, trip_id, "fuel_receipt")

        # 2. Save copy for financial reconciliation
        date_str = datetime.now().strftime("%Y-%m-%d")
        month_str = datetime.now().strftime("%Y-%m")
        month_dir = os.path.join(self.financial_dir, month_str)
        os.makedirs(month_dir, exist_ok=True)

        recon_filename = f"{date_str}_{vehicle_id}_Rs{cost}.jpg"
        recon_path = os.path.join(month_dir, recon_filename)
        with open(recon_path, "wb") as f:
            f.write(file_content)

        return rel_path

    def save_expense_receipt(
        self, file_content, driver_name, vehicle_id, expense_amount
    ):
        date_str = datetime.now().strftime("%Y-%m-%d")
        safe_name = "".join([c if c.isalnum() else "_" for c in driver_name])
        filename = f"{date_str}_{safe_name}_{vehicle_id}_Rs{expense_amount}.jpg"
        filepath = os.path.join(self.expense_dir, filename)
        with open(filepath, "wb") as f:
            f.write(file_content)
        return f"02_Expense_Claims/{filename}"

    def save_incident_report(self, file_content, driver_name, vehicle_id):
        date_str = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        filename = f"{date_str}_{vehicle_id}_Damage.jpg"
        filepath = os.path.join(self.incident_dir, filename)
        with open(filepath, "wb") as f:
            f.write(file_content)
        return f"04_Incident_Reports/{filename}"
