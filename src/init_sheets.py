import os

from dotenv import load_dotenv

from services.sheets_service import SheetsService

load_dotenv()

def init():
    service = SheetsService()
    if not service.spreadsheet:
        print(
            "❌ Could not connect to Spreadsheet. "
            "Check your .env and credentials.json"
        )
        return

    sheets_to_create = {
        "Dashboard": ["Metric", "Value", "Unit"],
        "Master_Vehicles": [
            "VehicleID", "LicensePlate", "VendorID", "Last_Odometer", "Status"
        ],
        "Master_Drivers": ["DriverID", "Name", "License", "VendorID", "Phone", "Status"],
        "Trips": [
            "TripID", "Date", "VendorID", "DriverID", "VehicleID",
            "Start_Time", "End_Time", "Duration_Mins",
            "Start_Location", "End_Location",
            "Start_Odometer", "End_Odometer", "Distance", 
            "Fuel_Liters", "Fuel_Cost", "Other_Expenses", "Revenue", "Net_Profit",
            "Driver_Score",
            "Start_Image", "End_Image", "Receipt_Image",
            "Flag", "Remarks"
        ],
        "Attendance": [
            "Date", "DriverID", "VendorID", "First_CheckIn",
            "Last_Activity", "Status", "Target_Type", "Target_Value"
        ],
        "Daily_Summary": [
            "Date", "VehicleID", "DriverID", "TripsCount", "TotalKM", 
            "TotalFuelCost", "TotalOtherExpenses", "TotalRevenue", "NetProfit", 
            "FlagsCount", "DriverScoreAvg", "Status"
        ]
    }

    for name, headers in sheets_to_create.items():
        try:
            # Try to get or create
            try:
                ws = service.spreadsheet.worksheet(name)
                print(f"✅ Sheet '{name}' already exists.")
            except Exception:
                ws = service.spreadsheet.add_worksheet(
                    title=name, rows="1000", cols="20"
                )
                print(f"🆕 Created sheet '{name}'.")
            
            # Set headers if empty
            if not ws.row_values(1):
                ws.insert_row(headers, 1)
                print(f"📝 Added headers to '{name}'.")
            
            # Specific logic for Dashboard
            if name == "Dashboard":
                setup_dashboard(ws)
                
        except Exception as e:
            print(f"⚠️ Error with sheet '{name}': {e}")

def setup_dashboard(ws):
    """Sets up KPI formulas and formatting for the Dashboard sheet"""
    kpis = [
        ["TOTAL FLEET DISTANCE", "=SUM(Trips!M:M)", "KM"],
        ["TOTAL FUEL CONSUMED", "=SUM(Trips!N:N)", "Liters"],
        ["TOTAL REVENUE", "=SUM(Trips!Q:Q)", "INR"],
        ["NET PROFIT", "=SUM(Trips!R:R)", "INR"],
        ["TOTAL FLAGGED TRIPS", '=COUNTIF(Trips!W:W, "*🚨*")', "Trips"],
        ["ACTIVE TRIPS", '=COUNTIF(Master_Vehicles!E:E, "On Trip")', "Vehicles"]
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
