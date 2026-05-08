import os
import sys
from datetime import datetime, timedelta

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from services.sheets_service import SheetsService
from services.attendance_service import AttendanceService

def wipe_and_seed() -> None:
    service = SheetsService()
    att_service = AttendanceService(service)
    if not service.spreadsheet:
        print("Could not connect to Spreadsheet.")
        return

    # 1. Sheets to CLEAR
    transactional_sheets = ["Trips", "Attendance", "Daily_Summary", "Monthly_Payroll", "Master_Drivers", "Master_Vehicles"]
    
    for name in transactional_sheets:
        try:
            ws = service.get_sheet(name)
            rows = len(ws.get_all_values())
            if rows > 1:
                ws.delete_rows(2, rows)
                print(f"Cleared data from {name}")
        except Exception as e:
            print(f"Error clearing {name}: {e}")

    # 2. Seed Master_Clients
    try:
        ws = service.get_sheet("Master_Clients")
        rows = len(ws.get_all_values())
        if rows > 1:
            ws.delete_rows(2, rows)
        ws.append_row(["C-XGAT", "XGAT Travel Agencies", "B2B Fixed", 800, 0])
        print("Seeded Client: XGAT Travel Agencies (800)")
    except Exception as e:
        print(f"Error seeding Master_Clients: {e}")

    # 3. Seed Master_Drivers & Vehicles (The Foundations)
    try:
        # DriverID, Name, License, ClientID, Phone, Base_Salary, Status
        driver_id = 12345678 # Test ID
        ws_drivers = service.get_sheet("Master_Drivers")
        ws_drivers.append_row([driver_id, "Srikar", "TS-09-2026", "C-XGAT", "9988776655", 27000, "Active"])
        
        # VehicleID, LicensePlate, ClientID, Last_Odometer, Status
        ws_vech = service.get_sheet("Master_Vehicles")
        ws_vech.append_row(["V-001", "TS 08 AB 1234", "C-XGAT", 1000, "Idle"])
        print(f"Seeded Driver 'Srikar' ({driver_id}) and Vehicle 'V-001'")
    except Exception as e:
        print(f"Error seeding Drivers/Vehicles: {e}")

    # 4. Seed Historical Attendance & Live Payroll (The Magic)
    import time
    print("Simulating 2 days of perfect performance (with rate-limit safety)...")
    today = datetime.now()
    for i in range(2):
        date_str = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        # Mark as Present
        att_service.mark_status(driver_id, "Present", date_str)
        time.sleep(2) # Safety delay
        
        # Update progress to 5 trips
        att_service.update_attendance_progress(driver_id, 5.0) 
        print(f"  -> Processed attendance for {date_str}")
        time.sleep(2) # Safety delay

    print("\nSystem wiped and re-seeded successfully with Live Payroll active!")

if __name__ == "__main__":
    wipe_and_seed()
