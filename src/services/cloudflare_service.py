import io
import logging
import os
import zipfile
from datetime import datetime

import boto3
from botocore.config import Config
from PIL import Image

logger = logging.getLogger(__name__)


class CloudflareR2Service:
    def __init__(self):
        self.bucket_name = os.getenv("CLOUDFLARE_R2_BUCKET")
        self.account_id = os.getenv("CLOUDFLARE_R2_ACCOUNT_ID")
        self.access_key = os.getenv("CLOUDFLARE_R2_ACCESS_KEY")
        self.secret_key = os.getenv("CLOUDFLARE_R2_SECRET_KEY")
        self.public_url = os.getenv("CLOUDFLARE_R2_PUBLIC_URL", "").rstrip("/")

        # R2 Endpoint URL
        self.endpoint_url = f"https://{self.account_id}.r2.cloudflarestorage.com"

        self.s3_client = boto3.client(
            service_name="s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name="auto",  # Cloudflare R2 requires "auto" region
            config=Config(signature_version="s3v4"),
        )

    def _compress_image(self, file_content, max_size_kb=500):
        """Resizes and compresses image to stay under target KB size."""
        img = Image.open(io.BytesIO(file_content))

        # Convert to RGB if necessary (e.g. for PNGs or RGBA)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        quality = 85
        output = io.BytesIO()

        while True:
            output.seek(0)
            output.truncate()
            img.save(output, format="JPEG", quality=quality, optimize=True)
            if output.tell() <= max_size_kb * 1024 or quality <= 10:
                break
            quality -= 10  # Reduce quality iteratively

        return output.getvalue()

    def upload_file(self, file_content, driver_name, trip_id, image_type):
        """Uploads a file to Cloudflare R2 bucket."""
        try:
            # Compress before upload
            compressed_content = self._compress_image(file_content)

            date_str = datetime.now().strftime("%Y-%m-%d")
            safe_name = "".join([c if c.isalnum() else "_" for c in driver_name])

            # Key format: trips/YYYY-MM-DD/DriverName/TripID/image_type.jpg
            key = f"trips/{date_str}/{safe_name}/{trip_id}/{image_type}.jpg"

            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=compressed_content,
                ContentType="image/jpeg",
            )

            logger.info(f"✅ Successfully uploaded image to R2: {key}")

            if self.public_url:
                return f"{self.public_url}/{key}"
            return key  # Fallback to key if no public URL configured
        except Exception as e:
            logger.error(f"❌ Error uploading to R2: {e}")
            return None

    def save_kyc_document(self, file_content, driver_name):
        try:
            # Compress before upload
            compressed_content = self._compress_image(file_content)

            safe_name = "".join([c if c.isalnum() else "_" for c in driver_name])
            key = f"compliance/kyc/{safe_name}_license.jpg"

            self.s3_client.put_object(
                Bucket=self.bucket_name, Key=key, Body=compressed_content, ContentType="image/jpeg"
            )
            logger.info(f"✅ Successfully uploaded KYC document for {driver_name}: {key}")
            return f"{self.public_url}/{key}" if self.public_url else key
        except Exception as e:
            logger.error(f"❌ Error uploading KYC: {e}")
            return None

    def save_fuel_receipt(self, file_content, driver_name, trip_id, vehicle_id, cost):
        try:
            # Compress before upload
            compressed_content = self._compress_image(file_content)

            date_str = datetime.now().strftime("%Y-%m-%d")
            key = f"finance/fuel/{date_str}_{vehicle_id}_Rs{cost}.jpg"

            self.s3_client.put_object(
                Bucket=self.bucket_name, Key=key, Body=compressed_content, ContentType="image/jpeg"
            )
            # Also upload as part of the trip (this will also compress)
            self.upload_file(file_content, driver_name, trip_id, "fuel_receipt")

            logger.info(f"✅ Successfully uploaded fuel receipt: {key}")
            return f"{self.public_url}/{key}" if self.public_url else key
        except Exception as e:
            logger.error(f"❌ Error uploading fuel receipt: {e}")
            return None

    def save_expense_receipt(self, file_content, driver_name, vehicle_id, expense_amount):
        try:
            # Compress before upload
            compressed_content = self._compress_image(file_content)

            date_str = datetime.now().strftime("%Y-%m-%d")
            safe_name = "".join([c if c.isalnum() else "_" for c in driver_name])
            key = f"finance/expenses/{date_str}_{safe_name}_{vehicle_id}_Rs{expense_amount}.jpg"

            self.s3_client.put_object(
                Bucket=self.bucket_name, Key=key, Body=compressed_content, ContentType="image/jpeg"
            )
            logger.info(f"✅ Successfully uploaded expense receipt: {key}")
            return f"{self.public_url}/{key}" if self.public_url else key
        except Exception as e:
            logger.error(f"❌ Error uploading expense receipt: {e}")
            return None

    def save_incident_report(self, file_content, driver_name, vehicle_id):
        try:
            # Compress before upload
            compressed_content = self._compress_image(file_content)

            date_str = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            key = f"incidents/{date_str}_{vehicle_id}_damage.jpg"

            self.s3_client.put_object(
                Bucket=self.bucket_name, Key=key, Body=compressed_content, ContentType="image/jpeg"
            )
            logger.info(f"✅ Successfully uploaded incident report: {key}")
            return f"{self.public_url}/{key}" if self.public_url else key
        except Exception as e:
            logger.error(f"❌ Error uploading incident report: {e}")
            return None

    def generate_period_zip(self, prefix):
        """Fetches all files under a prefix and returns a ZIP file in memory."""
        try:
            logger.info(f"🔍 Auditing R2 Bucket: {self.bucket_name} for prefix: {prefix}")

            # Debug: List EVERYTHING in the bucket to see what's actually there
            debug_list = self.s3_client.list_objects_v2(Bucket=self.bucket_name, MaxKeys=10)
            if "Contents" in debug_list:
                keys = [obj["Key"] for obj in debug_list["Contents"]]
                logger.info(f"📁 Current files in bucket (sample): {keys}")
            else:
                logger.warning("📭 Bucket appears to be empty during audit.")

            response = self.s3_client.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix)

            if "Contents" not in response:
                logger.warning(f"⚠️ No files found for prefix {prefix}")
                return None

            count = len(response["Contents"])
            logger.info(f"📦 Found {count} photos. Generating ZIP...")

            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zip_file:
                for obj in response["Contents"]:
                    file_key = obj["Key"]
                    file_data = self.s3_client.get_object(Bucket=self.bucket_name, Key=file_key)["Body"].read()
                    # Flatten folder structure in ZIP for easier viewing
                    zip_filename = file_key.replace("/", "_")
                    zip_file.writestr(zip_filename, file_data)

            zip_buffer.seek(0)
            return zip_buffer
        except Exception as e:
            logger.error(f"❌ Error generating ZIP: {e}")
            return None

    def flag_trip_images(self, date_str, driver_name, trip_id):
        """Flags trip images for audit by logging them."""
        # In R2 we just log the flagging event as we don't have 'starring'
        prefix = f"trips/{date_str}/{driver_name}/{trip_id}"
        logger.warning(f"🚩 Trip Flagged for Audit: {prefix}")
        # Optionally, we could copy these to a 'flagged/' folder here
        return True
