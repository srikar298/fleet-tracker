import os
from datetime import datetime
from typing import Any

from dotenv import load_dotenv

from services.sheets_service import SheetsService

load_dotenv()


def generate_daily_summary(target_date: str | None = None) -> None:
    if target_date is None:
        target_date = datetime.now().strftime("%Y-%m-%d")

    print(f"Generating Daily Summary for {target_date}...")
    sheets = SheetsService()

    try:
        trips_ws = sheets.spreadsheet.worksheet("Trips")
        all_trips = trips_ws.get_all_records()
    except Exception as e:
        print(f"Error accessing Trips sheet: {e}")
        return

    # Filter trips by date
    today_trips = [t for t in all_trips if t.get("Date") == target_date or t.get("date") == target_date]

    if not today_trips:
        print("No trips found for today.")
        return

    # Group by Vehicle
    summary_data: dict[Any, dict[str, Any]] = {}
    for t in today_trips:
        vid = t.get("VehicleID") or t.get("vehicle_id")
        did = t.get("DriverID") or t.get("driver_id")

        if vid not in summary_data:
            summary_data[vid] = {
                "DriverID": did,
                "TripsCount": 0,
                "TotalKM": 0.0,
                "TotalFuelCost": 0.0,
                "TotalOtherExpenses": 0.0,
                "TotalRevenue": 0.0,
                "FlagsCount": 0,
                "Scores": [],
            }

        summary_data[vid]["TripsCount"] += 1
        summary_data[vid]["TotalKM"] += float(t.get("Distance", 0))
        summary_data[vid]["TotalFuelCost"] += float(t.get("Fuel_Cost", 0) or t.get("fuel_cost", 0))
        summary_data[vid]["TotalOtherExpenses"] += float(t.get("Other_Expenses", 0) or t.get("other_expenses", 0))
        summary_data[vid]["TotalRevenue"] += float(t.get("Revenue", 0) or t.get("revenue", 0))

        flag = t.get("Flag", "") or t.get("flag", "")
        if flag and "OK" not in str(flag):
            summary_data[vid]["FlagsCount"] += 1

        score = t.get("Driver_Score") or t.get("driver_score", 100)
        summary_data[vid]["Scores"].append(float(score))

    # Write to Daily_Summary sheet
    for vid, data in summary_data.items():
        net_profit = data["TotalRevenue"] - data["TotalFuelCost"] - data["TotalOtherExpenses"]
        avg_score = sum(data["Scores"]) / len(data["Scores"]) if data["Scores"] else 100.0

        status = "Good"
        if avg_score < 70 or data["FlagsCount"] > 1:
            status = "Risky"
        if net_profit < 0:
            status = "Loss"

        row = [
            target_date,
            vid,
            data["DriverID"],
            data["TripsCount"],
            data["TotalKM"],
            data["TotalFuelCost"],
            data["TotalOtherExpenses"],
            data["TotalRevenue"],
            net_profit,
            data["FlagsCount"],
            round(avg_score, 1),
            status,
        ]

        sheets.append_row("Daily_Summary", row)
        print(f"✅ Added summary for {vid} -> Net Profit: ₹{net_profit} | Status: {status}")


if __name__ == "__main__":
    import sys

    sys.path.append(os.path.join(os.getcwd(), "src"))
    generate_daily_summary()
