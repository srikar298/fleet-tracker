import os
from dotenv import load_dotenv
from services.sheets_service import SheetsService

load_dotenv()

def wipe_and_seed() -> None:
    service = SheetsService()
    if not service.spreadsheet:
        print("❌ Could not connect to Spreadsheet.")
        return

    # 1. Define Headers for all sheets to ensure alignment
    schemas = {
        "Trips": [
            "TripID", "Date", "TripType", "Client_Name", "ClientID", "VehicleID", "DriverID", 
            "Distance", "Client_Billed", "Driver_Payout", "Fuel_Cost", "Other_Expenses", 
            "Gross_Margin", "Net_Margin_Percentage", "Driver_Score", "Flag", "Remarks", 
            "Start_Time", "End_Time", "Duration", "Start_Odometer", "End_Odometer", 
            "Fuel_Liters", "Start_Image", "End_Image", "Fuel_Image", "Expense_Image", 
            "Start_Location", "End_Location"
        ],
        "Master_Vehicles": [
            "VehicleID", "LicensePlate", "VendorID", "Last_Odometer", "Status"
        ],
        "Master_Drivers": [
            "DriverID", "Name", "License", "License_Photo", "ClientID", "Phone", "Base_Salary", "Status"
        ],
        "Master_Clients": [
            "ClientID", "Client_Name", "Client_Billed_Per_Trip", "Driver_Payout_Per_Trip", "Base_Distance", "Extra_Distance_Rate"
        ],
        "Attendance": [
            "Date", "DriverID", "Name", "ClientID", "Target_Type", "Target_Value", "Base_Salary", "Today_Base", "Completed_Value", "Achieved", "Today_Earnings"
        ],
        "Payroll": [
            "Month", "DriverID", "Name", "Base_Salary", "Working_Days", "Total_Completed", "Bonus", "Net_Payout"
        ]
    }

    print("Starting full database wipe and re-alignment...")

    for sheet_name, headers in schemas.items():
        try:
            ws = service.spreadsheet.worksheet(sheet_name)
            # Clear everything (Rows 1 to 1000, Columns A to AC)
            ws.clear()
            # Set Headers
            ws.insert_row(headers, 1)
            print(f"Reset headers for '{sheet_name}'.")
        except Exception as e:
            print(f"Error resetting '{sheet_name}': {e}")

    # 2. Seed Master Data
    try:
        # Seed Client
        mc = service.spreadsheet.worksheet("Master_Clients")
        mc.insert_row(["C-XGAT", "Xpress Global", 500, 400, 50, 10], 2)
        print("Seeded Client: Xpress Global")

        # Seed Vehicle
        mv = service.spreadsheet.worksheet("Master_Vehicles")
        mv.insert_row(["V-001", "KA-03-AN-6115", "V-MASTER", 0, "Idle"], 2)
        print("Seeded Vehicle: KA-03-AN-6115 (Ertiga)")

        # Seed Driver
        md = service.spreadsheet.worksheet("Master_Drivers")
        md.insert_row(["8422295203", "vijay", "PENDING", "PENDING", "C-XGAT", "PENDING", 27000, "Active"], 2)
        print("Seeded Driver: vijay")

    except Exception as e:
        print(f"Error seeding master data: {e}")

    print("\nDatabase alignment and seeding complete!")

if __name__ == "__main__":
    wipe_and_seed()
