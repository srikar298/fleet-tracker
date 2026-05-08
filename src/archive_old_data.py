import os
import shutil
from datetime import datetime, timedelta

from dotenv import load_dotenv

load_dotenv()


def archive_old_data() -> None:
    print("Starting data archival process...")
    base_dir = os.path.join(os.getcwd(), "trip_images")
    archive_dir = os.path.join(os.getcwd(), "05_Archived_Data")
    os.makedirs(archive_dir, exist_ok=True)

    thirty_days_ago = datetime.now() - timedelta(days=30)

    if not os.path.exists(base_dir):
        print("No trip_images directory found.")
        return

    archived_count = 0

    for item in os.listdir(base_dir):
        item_path = os.path.join(base_dir, item)
        if os.path.isdir(item_path):
            try:
                # trip_images subfolders are expected to be YYYY-MM-DD
                folder_date = datetime.strptime(item, "%Y-%m-%d")
                if folder_date < thirty_days_ago:
                    archive_name = os.path.join(archive_dir, f"Archive_{item}")
                    print(f"Archiving {item} to {archive_name}.zip")

                    # Create zip file
                    shutil.make_archive(archive_name, "zip", item_path)

                    # Remove original folder after successful zip
                    shutil.rmtree(item_path)
                    archived_count += 1
            except ValueError:
                # If it's not a date folder (like Flagged_Review), skip it
                pass

    print(f"Archival complete. {archived_count} folders archived.")


if __name__ == "__main__":
    archive_old_data()
