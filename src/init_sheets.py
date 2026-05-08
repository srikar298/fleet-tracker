import os
from typing import Any

from dotenv import load_dotenv

from services.sheets_service import SheetsService

load_dotenv()


def init() -> None:
    service = SheetsService()
    if not service.spreadsheet:
        print("❌ Could not connect to Spreadsheet. Check your .env and credentials.json")
        return

    sheets_to_create = {
        "Dashboard": ["Metric", "Value", "Unit"],
        "Master_Vehicles": ["VehicleID", "LicensePlate", "ClientID", "Last_Odometer", "Status"],
        "Master_Drivers": ["DriverID", "Name", "License", "ClientID", "Phone", "Status"],
        "Master_Clients": ["ClientID", "Client_Name", "Contract_Type", "Client_Billed_Per_Trip", "Driver_Payout_Per_Trip"],
        "Trips": [
            "TripID", "Date", "Client_Name", "ClientID", "DriverID", "VehicleID", 
            "Start_Time", "End_Time", "Duration_Mins", "Start_Location", "End_Location", 
            "Start_Odometer", "End_Odometer", "Distance", "Fuel_Liters", "Fuel_Cost", 
            "Other_Expenses", "Client_Billed_Amount", "Driver_Payout_Amount", "Gross_Margin", 
            "Net_Margin_Percentage", "Driver_Score", "Start_Image", "End_Image", "Receipt_Image", "Flag", "Remarks"
        ],
        "Attendance": ["Date", "DriverID", "ClientID", "First_CheckIn", "Last_Activity", "Status", "Target_Type", "Target_Value"],
        "Daily_Summary": ["Date", "VehicleID", "DriverID", "TripsCount", "TotalKM", "TotalFuelCost", "TotalOtherExpenses", "TotalBilled", "TotalPayout", "NetMargin", "FlagsCount", "DriverScoreAvg", "Status"],
    }

    for name, headers in sheets_to_create.items():
        try:
            # Check if worksheet exists
            worksheet_list = [w.title for w in service.spreadsheet.worksheets()]
            
            if name in worksheet_list:
                ws = service.spreadsheet.worksheet(name)
                print(f"Sheet '{name}' verified.")
            else:
                ws = service.spreadsheet.add_worksheet(title=name, rows="1000", cols="26")
                print(f"Created new sheet: {name}")

            # Check for headers
            current_headers = ws.row_values(1)
            if not current_headers:
                ws.insert_row(headers, 1)
                print(f"Initialized headers for {name}")
            elif len(current_headers) != len(headers):
                print(f"Warning: {name} headers mismatch. Current: {len(current_headers)}, Expected: {len(headers)}")

            if name == "Dashboard":
                setup_dashboard(ws)

        except Exception as e:
            print(f"Error handling sheet {name}: {str(e)}")


def setup_dashboard(ws: Any) -> None:
    """Sets up KPI formulas and formatting for the Dashboard sheet"""
    kpis = [
        ["TOTAL FLEET DISTANCE", "=SUM(Trips!M:M)", "KM"],
        ["TOTAL FUEL CONSUMED", "=SUM(Trips!N:N)", "Liters"],
        ["TOTAL REVENUE", "=SUM(Trips!Q:Q)", "INR"],
        ["NET PROFIT", "=SUM(Trips!R:R)", "INR"],
        ["TOTAL FLAGGED TRIPS", '=COUNTIF(Trips!W:W, "*🚨*")', "Trips"],
        ["ACTIVE TRIPS", '=COUNTIF(Master_Vehicles!E:E, "On Trip")', "Vehicles"],
    ]

    # Starting from row 3 to leave space for a header
    ws.update("A3:C7", kpis, raw=False)
    print("📈 Dashboard KPIs initialized with formulas.")

    print("\n🚀 Initialization complete! Your Google Sheet is ready.")


if __name__ == "__main__":
    # Add src to path if running from root
    import sys

    sys.path.append(os.path.join(os.getcwd(), "src"))
    init()
