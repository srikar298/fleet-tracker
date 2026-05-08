from dotenv import load_dotenv

from services.sheets_service import SheetsService

load_dotenv()


def wipe_and_seed():
    service = SheetsService()
    if not service.spreadsheet:
        print("Could not connect to Spreadsheet.")
        return

    sheets_to_wipe = [
        "Trips",
        "Master_Vehicles",
        "Master_Drivers",
        "Attendance",
        "Daily_Summary",
    ]

    for name in sheets_to_wipe:
        try:
            ws = service.spreadsheet.worksheet(name)
            # Clear everything from row 2 onwards
            ws.batch_clear(["A2:Z1000"])
            print(f"Wiped data from '{name}'.")
        except Exception as e:
            print(f"Error wiping '{name}': {e}")

    # Seed Vehicle
    try:
        mv = service.spreadsheet.worksheet("Master_Vehicles")
        # Headers: VehicleID, LicensePlate, VendorID, Last_Odometer, Status
        vehicle_data = ["V-001", "KA-03-AN-6115", "V-MASTER", 0, "Idle"]
        mv.insert_row(vehicle_data, 2)
        print("Seeded Vehicle: KA-03-AN-6115")
    except Exception as e:
        print(f"Error seeding vehicle: {e}")

    # Seed Driver
    try:
        md = service.spreadsheet.worksheet("Master_Drivers")
        # Headers: DriverID, Name, License, VendorID, Phone, Status
        driver_data = ["DUMMY_VIJAY", "vijay", "PENDING", "V-MASTER", "PENDING", "Active"]
        md.insert_row(driver_data, 2)
        print("Seeded Driver: vijay")
    except Exception as e:
        print(f"Error seeding driver: {e}")

    print("\nDatabase wiped and re-seeded with new fleet data.")


if __name__ == "__main__":
    wipe_and_seed()
