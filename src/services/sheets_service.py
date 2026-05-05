import os

import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

load_dotenv()

class SheetsService:
    def __init__(self):
        self.scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        self.credentials_path = os.getenv("SERVICE_ACCOUNT_FILE", "credentials.json")
        self.sheet_id = os.getenv("GOOGLE_SHEETS_ID")
        
        try:
            self.creds = Credentials.from_service_account_file(
                self.credentials_path, 
                scopes=self.scope
            )
            self.client = gspread.authorize(self.creds)
            self.spreadsheet = self.client.open_by_key(self.sheet_id)
        except Exception as e:
            print(f"Failed to initialize Sheets Service: {e}")
            self.spreadsheet = None

    def get_sheet(self, name):
        if not self.spreadsheet:
            return None
        return self.spreadsheet.worksheet(name)

    def append_row(self, sheet_name, data):
        sheet = self.get_sheet(sheet_name)
        if sheet:
            try:
                # Find the next available row by counting non-empty cells in Column A
                col_a = sheet.col_values(1)
                next_row = len(col_a) + 1
                
                # Format formulas with the exact row number
                for i in range(len(data)):
                    if isinstance(data[i], str) and "{row}" in data[i]:
                        data[i] = data[i].format(row=next_row)
                        
                # Update the row directly instead of using append_row to support formulas
                sheet.update(f"A{next_row}", [data], value_input_option="USER_ENTERED")
                return True
            except Exception as e:
                print(f"Error writing to sheet {sheet_name}: {e}")
                return False
        return False

    def get_vehicle_last_odo(self, vehicle_id):
        """Fetches the last recorded odometer for a vehicle from Master_Vehicles"""
        sheet = self.get_sheet("Master_Vehicles")
        if not sheet:
            return 0
        
        records = sheet.get_all_records()
        for record in records:
            if str(record.get("VehicleID")) == str(vehicle_id):
                return record.get("Last_Odometer", 0)
        return 0

    def get_all_vehicles(self):
        """Returns a list of all vehicle IDs"""
        sheet = self.get_sheet("Master_Vehicles")
        if not sheet:
            return ["V-001", "V-002", "V-003"] # Fallback
        
        records = sheet.get_all_records()
        return [str(v.get("VehicleID")) for v in records if v.get("VehicleID")]

    def update_vehicle_status(self, vehicle_id, odo, status="Idle"):
        """Updates the status and odo of a vehicle in Master_Vehicles"""
        sheet = self.get_sheet("Master_Vehicles")
        if not sheet:
            return
        
        records = sheet.get_all_records()
        for i, record in enumerate(records, start=2):
            if str(record.get("VehicleID")) == str(vehicle_id):
                sheet.update_cell(i, 4, odo) # Last_Odometer
                sheet.update_cell(i, 5, status) # Status
                return

    def register_driver(self, driver_id, name, license, phone, vendor_id="V-MASTER"):
        """Registers a new driver in Master_Drivers"""
        return self.append_row("Master_Drivers", [
            driver_id, name, license, vendor_id, phone, "Active"
        ])

    def record_trip(self, trip_data):
        """Appends a final trip record to the Trips sheet"""
        return self.append_row("Trips", [
            trip_data.get("trip_id"),
            trip_data.get("date"),
            trip_data.get("vendor_id"),
            trip_data.get("driver_id"),
            trip_data.get("vehicle_id"),
            trip_data.get("start_time"),
            trip_data.get("end_time"),
            trip_data.get("duration"),
            trip_data.get("start_location"),
            trip_data.get("end_location"),
            trip_data.get("start_odo"),
            trip_data.get("end_odo"),
            trip_data.get("distance"),
            trip_data.get("fuel_liters"),
            trip_data.get("fuel_cost"),
            trip_data.get("other_expenses"),
            trip_data.get("revenue"),
            trip_data.get("net_profit"),
            trip_data.get("driver_score"),
            trip_data.get("start_image"),
            trip_data.get("end_image"),
            trip_data.get("fuel_image"),
            trip_data.get("flag"),
            trip_data.get("remarks")
        ])

    def get_driver_today_summary(self, driver_id):
        """Calculates today's summary for a specific driver from Trips sheet"""
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        sheet = self.get_sheet("Trips")
        if not sheet:
            return {"trips": 0, "km": 0, "fuel": 0, "revenue": 0, "net": 0}
            
        records = sheet.get_all_records()
        trips = 0
        km = 0.0
        fuel = 0.0
        revenue = 0.0
        
        for r in records:
            # Match date and driver
            if (r.get("Date") == today or r.get("date") == today) and str(r.get("DriverID")) == str(driver_id):
                trips += 1
                try: km += float(r.get("Distance", 0))
                except: pass
                try: fuel += float(r.get("Fuel_Cost", 0))
                except: pass
                try: revenue += float(r.get("Revenue", 0))
                except: pass
                
        return {
            "trips": trips,
            "km": km,
            "fuel": fuel,
            "revenue": revenue,
            "net": revenue - fuel
        }

    def get_live_leaderboard(self):
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        
        att_sheet = self.get_sheet("Attendance")
        trips_sheet = self.get_sheet("Trips")
        master_drivers = self.get_sheet("Master_Drivers")
        
        if not att_sheet or not trips_sheet or not master_drivers:
            return "Unable to fetch leaderboard."
            
        driver_names = {str(d.get("DriverID")): d.get("Name", "Unknown") for d in master_drivers.get_all_records()}
        
        targets = {}
        for r in att_sheet.get_all_records():
            if r.get("Date") == today and r.get("Target_Type"):
                targets[str(r.get("DriverID"))] = {
                    "type": r.get("Target_Type"),
                    "value": float(r.get("Target_Value", 0))
                }
                
        progress = {did: {"trips": 0, "revenue": 0.0} for did in targets}
        for r in trips_sheet.get_all_records():
            if r.get("Date") == today or r.get("date") == today:
                did = str(r.get("DriverID"))
                if did in progress:
                    progress[did]["trips"] += 1
                    try: progress[did]["revenue"] += float(r.get("Revenue", 0))
                    except: pass
                    
        lb = []
        for did, tgt in targets.items():
            name = driver_names.get(did, "Driver")
            hit = 0
            if tgt["type"] == "Trips" and tgt["value"] > 0:
                hit = progress[did]["trips"] / tgt["value"]
            elif tgt["type"] == "Revenue" and tgt["value"] > 0:
                hit = progress[did]["revenue"] / tgt["value"]
            
            lb.append({"name": name, "pct": hit * 100, "type": tgt["type"]})
            
        lb.sort(key=lambda x: x["pct"], reverse=True)
        
        if not lb:
            return "No daily targets set yet! Start a trip to set your goal."
            
        text = "🏆 *Live Daily Leaderboard*\n\n"
        medals = ["🥇", "🥈", "🥉"]
        for i, driver in enumerate(lb[:5]):
            medal = medals[i] if i < 3 else "🌟"
            text += f"{medal} {driver['name']}: {driver['pct']:.1f}% of {driver['type']} Goal Hit\n"
            
        return text
