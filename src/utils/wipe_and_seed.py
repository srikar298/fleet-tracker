import os
import sys
from datetime import datetime

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from services.sheets_service import SheetsService

def wipe_and_seed() -> None:
    service = SheetsService()
    if not service.spreadsheet:
        print("Could not connect to Spreadsheet.")
        return

    # 1. Sheets to CLEAR (Wipe everything except headers)
    transactional_sheets = ["Trips", "Attendance", "Daily_Summary", "Monthly_Payroll", "Master_Drivers", "Master_Vehicles"]
    
    for name in transactional_sheets:
        try:
            ws = service.get_sheet(name)
            # Find last row
            rows = len(ws.get_all_values())
            if rows > 1:
                # Delete from row 2 onwards
                ws.delete_rows(2, rows)
                print(f"Cleared data from {name}")
            else:
                print(f"{name} was already empty.")
        except Exception as e:
            print(f"Error clearing {name}: {e}")

    # 2. Master_Clients (Clear and Seed XGAT)
    try:
        ws = service.get_sheet("Master_Clients")
        rows = len(ws.get_all_values())
        if rows > 1:
            ws.delete_rows(2, rows)
        
        # Seed XGAT
        # ClientID, Client_Name, Contract_Type, Client_Billed_Per_Trip, Driver_Payout_Per_Trip
        ws.append_row(["C-XGAT", "XGAT Travel Agencies", "B2B Fixed", 800, 0])
        print("Seeded Client: XGAT Travel Agencies (B2B Fixed: 800)")
    except Exception as e:
        print(f"Error seeding Master_Clients: {e}")

    print("\nSystem wiped and re-seeded successfully in the new enhanced format!")

if __name__ == "__main__":
    wipe_and_seed()
