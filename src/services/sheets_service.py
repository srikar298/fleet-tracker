import os
from typing import Any, Dict, List, Optional

import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

load_dotenv()


class SheetsService:
    def __init__(self) -> None:
        self.scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        self.credentials_path = os.getenv("SERVICE_ACCOUNT_FILE", "credentials.json")
        self.sheet_id = os.getenv("GOOGLE_SHEETS_ID")

        try:
            # Try to load from environment variable first (standard for Cloud/Railway)
            json_content = os.getenv("GOOGLE_CREDENTIALS_JSON")
            if json_content:
                import json

                info = json.loads(json_content)
                self.creds = Credentials.from_service_account_info(info, scopes=self.scope)
            else:
                self.creds = Credentials.from_service_account_file(self.credentials_path, scopes=self.scope)
            self.client = gspread.authorize(self.creds)
            self.spreadsheet: gspread.Spreadsheet | None = self.client.open_by_key(str(self.sheet_id))
        except Exception as e:
            print(f"Failed to initialize Sheets Service: {e}")
            self.spreadsheet = None

    def get_sheet(self, name: str) -> gspread.Worksheet | None:
        if not self.spreadsheet:
            return None
        return self.spreadsheet.worksheet(name)

    def get_records_safe(self, name: str) -> list[dict[str, Any]]:
        """Safely fetches all records from a worksheet."""
        sheet = self.get_sheet(name)
        if not sheet:
            return []
        try:
            return sheet.get_all_records()
        except Exception:
            return []

    def append_row(self, sheet_name: str, data: list[Any]) -> bool:
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

                # Update the row directly instead of using append_row to support formulas  # noqa: E501
                sheet.update(f"A{next_row}", [data], value_input_option="USER_ENTERED")  # type: ignore
                return True
            except Exception as e:
                print(f"Error writing to sheet {sheet_name}: {e}")
                return False
        return False

    def get_vehicle_last_odo(self, vehicle_id: str) -> Any:
        """Fetches the last recorded odometer for a vehicle from Master_Vehicles"""
        sheet = self.get_sheet("Master_Vehicles")
        if not sheet:
            return 0

        records = sheet.get_all_records()
        for record in records:
            if str(record.get("VehicleID")) == str(vehicle_id):
                return record.get("Last_Odometer", 0)
        return 0

    def get_all_vehicles(self) -> list[dict[str, str]]:
        """Returns a list of all vehicle data (ID and License Plate)"""
        sheet = self.get_sheet("Master_Vehicles")
        if not sheet:
            return [{"id": "V-001", "plate": "MH12-1234"}]  # Fallback

        records = sheet.get_all_records()
        return [
            {"id": str(v.get("VehicleID")), "plate": str(v.get("LicensePlate"))} for v in records if v.get("VehicleID")
        ]

    def get_vehicle_map(self) -> dict[str, str]:
        """Returns a dict mapping VehicleID to LicensePlate"""
        vehicles = self.get_all_vehicles()
        return {str(v["id"]): str(v["plate"]) for v in vehicles}

    def update_vehicle_status(self, vehicle_id: str, odo: Any, status: str = "Idle") -> None:
        """Updates the status and odo of a vehicle in Master_Vehicles"""
        sheet = self.get_sheet("Master_Vehicles")
        if not sheet:
            return

        records = sheet.get_all_records()
        for i, record in enumerate(records, start=2):
            if str(record.get("VehicleID")) == str(vehicle_id):
                sheet.update_cell(i, 4, odo)  # Last_Odometer
                sheet.update_cell(i, 5, status)  # Status
                return

    def get_driver_by_id(self, telegram_id: int) -> dict[str, Any] | None:
        """Fetches driver details by Telegram ID."""
        records = self.get_records_safe("Master_Drivers")
        for r in records:
            if str(r.get("DriverID")) == str(telegram_id):
                return r
        return None

    def get_client_rates(self, client_id: str) -> dict[str, Any]:
        """Fetches pricing rates for a client."""
        records = self.get_records_safe("Master_Clients")
        for r in records:
            if str(r.get("ClientID")) == str(client_id):
                return {
                    "client_name": str(r.get("Client_Name", "General B2B")),
                    "client_billed": float(r.get("Client_Billed_Per_Trip") or 0),
                    "driver_payout": float(r.get("Driver_Payout_Per_Trip") or 0),
                }
        return {
            "client_name": "General B2B",
            "client_billed": 0,
            "driver_payout": 0,
        }

    def add_client_rate(self, c_id: str, client_name: str, billed: float, payout: float) -> bool:
        """Adds or updates a client's pricing rate in Master_Clients."""
        ws = self.get_sheet("Master_Clients")
        if not ws:
            return False
        
        # Check if exists to update
        records = ws.get_all_records()
        for i, r in enumerate(records, 2):
            if str(r.get("ClientID")) == str(c_id):
                ws.update(values=[[c_id, client_name, "B2B", billed, payout]], range_name=f"A{i}:E{i}")
                return True
        
        # Otherwise append
        return self.append_row("Master_Clients", [c_id, client_name, "B2B", billed, payout])

    def register_driver(self, driver_id: int, name: str, license: str, phone: str, client_id: str = "C-MASTER") -> bool:
        """Registers a new driver in Master_Drivers"""
        return self.append_row("Master_Drivers", [driver_id, name, license, client_id, phone, "Active"])

    def record_trip(self, trip_data: dict[str, Any]) -> bool:
        """Appends a final trip record to the Trips sheet matching B2B headers exactly"""
        return self.append_row(
            "Trips",
            [
                trip_data.get("trip_id"),           # TripID
                trip_data.get("date"),              # Date
                trip_data.get("client_name", "N/A"),# Client_Name
                trip_data.get("client_id"),         # ClientID
                trip_data.get("driver_id"),         # DriverID
                trip_data.get("vehicle_id"),        # VehicleID
                trip_data.get("start_time"),        # Start_Time
                trip_data.get("end_time"),          # End_Time
                trip_data.get("duration"),          # Duration_Mins
                trip_data.get("start_location"),    # Start_Location
                trip_data.get("end_location"),      # End_Location
                trip_data.get("start_odo"),         # Start_Odometer
                trip_data.get("end_odo"),           # End_Odometer
                trip_data.get("distance"),          # Distance
                trip_data.get("fuel_liters"),       # Fuel_Liters
                trip_data.get("fuel_cost"),         # Fuel_Cost
                trip_data.get("other_expenses"),    # Other_Expenses
                trip_data.get("client_billed", 0),  # Client_Billed_Amount
                trip_data.get("driver_payout", 0),  # Driver_Payout_Amount
                trip_data.get("net_profit"),        # Gross_Margin
                "=IF(R{row}>0, T{row}/R{row}, 0)",  # Net_Margin_Percentage
                trip_data.get("driver_score"),      # Driver_Score
                trip_data.get("start_image"),       # Start_Image
                trip_data.get("end_image"),         # End_Image
                trip_data.get("fuel_image"),        # Receipt_Image
                trip_data.get("flag"),              # Flag
                trip_data.get("remarks"),           # Remarks
            ],
        )

    def get_driver_today_summary(self, driver_id: int) -> dict[str, Any]:
        """Calculates today's summary for a specific driver from Trips sheet"""
        from datetime import datetime

        today = datetime.now().strftime("%Y-%m-%d")
        sheet = self.get_sheet("Trips")
        if not sheet:
            return {"trips": 0, "km": 0, "fuel": 0, "revenue": 0, "net": 0, "trip_list": []}

        records = sheet.get_all_records()
        trips = 0
        km = 0.0
        fuel = 0.0
        revenue = 0.0
        trip_list = []

        for r in records:
            # Match date and driver (Case-insensitive keys)
            r_date = r.get("Date") or r.get("date") or r.get("DATE")
            r_driver = r.get("DriverID") or r.get("driver_id") or r.get("Driver_ID") or r.get("driverid")

            if str(r_date) == today and str(r_driver) == str(driver_id):
                trips += 1
                try:
                    d = float(r.get("Distance") or r.get("distance") or 0)
                    km += d
                    trip_list.append(d)
                except (ValueError, TypeError):
                    pass
                try:
                    fuel += float(
                        r.get("Fuel_Cost")
                        or r.get("fuel_cost")
                        or r.get("Other_Expenses")
                        or r.get("other_expenses")
                        or 0
                    )
                except (ValueError, TypeError):
                    pass
                try:
                    rev_val = r.get("Driver_Payout_Amount") or r.get("Revenue") or r.get("revenue") or 0
                    revenue += float(rev_val)
                except (ValueError, TypeError):
                    pass

        return {
            "trips": trips,
            "km": km,
            "trip_list": trip_list,
        }

    def get_live_leaderboard(self, viewer_id: Optional[int] = None) -> str:
        from datetime import datetime

        today = datetime.now().strftime("%Y-%m-%d")
        trips_sheet = self.get_sheet("Trips")
        master_drivers_sheet = self.get_sheet("Master_Drivers")

        if not trips_sheet or not master_drivers_sheet:
            return "Unable to fetch leaderboard."

        # Map IDs to Names
        driver_names = {
            str(d.get("DriverID")): str(d.get("Name", "Unknown")) for d in master_drivers_sheet.get_all_records()
        }

        # Aggregate trips for today
        trip_counts: dict[str, int] = {str(did): 0 for did in driver_names}
        for r in trips_sheet.get_all_records():
            r_date = r.get("Date") or r.get("date")
            if str(r_date) == today:
                did = str(r.get("DriverID"))
                if did in trip_counts:
                    trip_counts[did] += 1

        # Create sorted list
        rankings: List[Dict[str, Any]] = []
        for did, count in trip_counts.items():
            if count > 0:
                rankings.append({"id": did, "name": driver_names.get(did, "Driver"), "trips": count})

        # Sort by trips (desc), then name
        rankings.sort(key=lambda x: (-int(x["trips"]), str(x["name"])))

        if not rankings:
            return "No trips recorded today yet! Be the first to top the leaderboard. 🏆"

        # Find viewer's rank
        viewer_rank = 0
        viewer_did = str(viewer_id) if viewer_id else ""
        for i, entry in enumerate(rankings, 1):
            if entry["id"] == viewer_did:
                viewer_rank = i
                break

        text = "🏆 *Live Trip Leaderboard (Today)*\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n\n"

        # Top 5
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for i, entry in enumerate(rankings[:5]):
            medal = medals[i]
            highlight = " (YOU)" if entry["id"] == viewer_did else ""
            text += f"{medal} *{entry['name']}*: `{entry['trips']} Trips`{highlight}\n"

        # Show viewer's specific stance if not in top 5
        if viewer_rank > 5:
            text += f"\n...\n"
            text += f"🎖 *Rank #{viewer_rank}*: You have `{trip_counts.get(viewer_did, 0)} Trips` today.\n"
        elif viewer_rank > 0:
            text += f"\n🚀 You are in the **Top {viewer_rank}**! Keep going!"
        else:
            text += f"\n💡 Start your first trip to enter the rankings!"

        text += f"\n\nTotal active drivers: `{len(rankings)}`"
        return text

    def get_fuel_efficiency_report(self) -> list[dict[str, Any]]:
        """Calculates KM/L per vehicle from the Trips sheet."""
        trips = self.get_records_safe("Trips")
        vehicles: dict[str, dict[str, float]] = {}

        for t in trips:
            v_id = str(t.get("VehicleID") or t.get("vehicle_id") or "")
            dist_val = t.get("Distance") or t.get("distance") or 0
            fuel_val = t.get("Fuel_Liters") or t.get("fuel_liters") or 0

            try:
                dist = float(dist_val)
                fuel = float(fuel_val)

                if v_id and fuel > 0:
                    if v_id not in vehicles:
                        vehicles[v_id] = {"dist": 0.0, "fuel": 0.0}
                    vehicles[v_id]["dist"] += dist
                    vehicles[v_id]["fuel"] += fuel
            except (ValueError, TypeError):
                continue

        report: list[dict[str, Any]] = []
        for v_id, stats in vehicles.items():
            if stats["fuel"] > 0:
                kml = stats["dist"] / stats["fuel"]
                report.append({"id": v_id, "kml": kml, "total_km": stats["dist"]})

        return sorted(report, key=lambda x: x["kml"], reverse=True)
