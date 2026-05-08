from datetime import datetime
from typing import Any

from services.sheets_service import SheetsService


class AttendanceService:
    def __init__(self, sheets_service: SheetsService) -> None:
        self.sheets = sheets_service

    def log_activity(self, driver_id: str | int, client_id: str) -> None:
        """Logs the first check-in or updates the last activity for a driver"""
        today = datetime.now().strftime("%Y-%m-%d")
        now_time = datetime.now().strftime("%H:%M:%S")

        sheet = self.sheets.get_sheet("Attendance")
        if not sheet:
            return

        records = sheet.get_all_records()
        for i, record in enumerate(records, start=2):
            if str(record.get("DriverID")) == str(driver_id) and record.get("Date") == today:
                sheet.update_cell(i, 5, now_time)
                return

        sheet.append_row([today, driver_id, client_id, now_time, now_time, "Present", "", ""])

    def get_daily_target(self, driver_id: str | int) -> dict[str, Any] | None:
        today = datetime.now().strftime("%Y-%m-%d")
        sheet = self.sheets.get_sheet("Attendance")
        if not sheet:
            return None
        for record in sheet.get_all_records():
            if str(record.get("DriverID")) == str(driver_id) and record.get("Date") == today:
                t_type = record.get("Target_Type")
                if t_type:
                    try:
                        val = float(record.get("Target_Value", 0))
                    except (ValueError, TypeError):
                        val = 0.0
                    return {
                        "type": t_type,
                        "value": val,
                    }
                return None
        return None

    def set_daily_target(self, driver_id: str | int, client_id: str, t_type: str, t_value: float) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        now_time = datetime.now().strftime("%H:%M:%S")
        sheet = self.sheets.get_sheet("Attendance")
        if not sheet:
            return

        records = sheet.get_all_records()
        for i, record in enumerate(records, start=2):
            if str(record.get("DriverID")) == str(driver_id) and record.get("Date") == today:
                sheet.update_cell(i, 7, t_type)
                sheet.update_cell(i, 8, t_value)
                return

        # If no check-in row exists, create it with 0 completed
        sheet.append_row(
            [
                today,
                driver_id,
                client_id,
                now_time,
                now_time,
                "Present",
                t_type,
                t_value,
                0,      # Completed_Value
                "No",   # Target_Achieved
                0       # Daily_Earnings
            ]
        )

    def update_attendance_progress(self, driver_id: str | int, amount: float = 1.0) -> None:
        """Updates trip count and calculates daily earnings based on target"""
        today = datetime.now().strftime("%Y-%m-%d")
        sheet = self.sheets.get_sheet("Attendance")
        if not sheet:
            return

        records = sheet.get_all_records()
        for i, record in enumerate(records, start=2):
            if str(record.get("DriverID")) == str(driver_id) and record.get("Date") == today:
                # 1. Update Completion
                current = float(record.get("Completed_Value") or 0)
                new_val = current + amount
                sheet.update_cell(i, 9, new_val)
                
                # 2. Update Target Status
                target = float(record.get("Target_Value") or 5.0)
                achieved = "Yes" if new_val >= target else "No"
                sheet.update_cell(i, 10, achieved)
                
                # 3. Calculate Daily Earnings
                # Fetch dynamic base salary
                driver_info = self.sheets.get_driver_by_id(driver_id)
                base_salary = 27000.0
                if driver_info and driver_info.get("Base_Salary"):
                    try:
                        base_salary = float(driver_info["Base_Salary"])
                    except (ValueError, TypeError):
                        pass

                daily_base = base_salary / 26.0
                incentive_per_trip = 100.0 # Extra money for trips > target
                
                earnings = daily_base
                if achieved == "No":
                    # Deduction logic: Pro-rata of base salary based on trips?
                    # Example: If only 3/5 done, they get 3/5 of daily pay
                    earnings = (new_val / target) * daily_base
                elif new_val > target:
                    # Bonus logic: Base + (Extra Trips * Incentive)
                    extra = new_val - target
                    earnings = daily_base + (extra * incentive_per_trip)
                
                sheet.update_cell(i, 11, round(earnings, 2))
                
                # 4. Update Monthly_Payroll Live
                self.update_monthly_payroll_live(driver_id, today[:7], earnings)
                return

        # --- AUTO-CREATE IF MISSING ---
        driver_info = self.sheets.get_driver_by_id(driver_id)
        base_salary = 27000.0
        if driver_info and driver_info.get("Base_Salary"):
            try:
                base_salary = float(driver_info["Base_Salary"])
            except (ValueError, TypeError):
                pass
        
        daily_base = base_salary / 26.0
        # Calculate earnings for the first trip
        # amount is the trips just added (usually 1.0)
        trips_done = amount
        target = 5.0
        earnings = (trips_done / target) * daily_base
        
        row_data = [
            today,
            driver_id,
            "Auto", # ClientID
            datetime.now().strftime("%H:%M:%S"), # Start
            datetime.now().strftime("%H:%M:%S"), # End
            "Present",
            "Trips", # Target_Type
            target,
            trips_done,
            "Yes" if trips_done >= target else "No",
            round(earnings, 2)
        ]
        sheet.append_row(row_data)
        self.update_monthly_payroll_live(driver_id, today[:7], earnings)

    def update_monthly_payroll_live(self, driver_id: str | int, month_str: str, daily_earnings: float) -> None:
        """Updates the Monthly_Payroll sheet in real-time"""
        payroll_ws = self.sheets.get_sheet("Monthly_Payroll")
        attendance_ws = self.sheets.get_sheet("Attendance")
        if not payroll_ws or not attendance_ws:
            return

        # 1. Aggregate Month Data from Attendance
        records = attendance_ws.get_all_records()
        present_days = 0
        total_extra_bonus = 0.0
        total_shortfall = 0.0
        
        # Fetch dynamic base salary
        driver_info = self.sheets.get_driver_by_id(driver_id)
        base_salary = 27000.0
        if driver_info and driver_info.get("Base_Salary"):
            try:
                base_salary = float(driver_info["Base_Salary"])
            except (ValueError, TypeError):
                pass
        daily_base = base_salary / 26.0
        
        for r in records:
            if str(r.get("DriverID")) == str(driver_id) and str(r.get("Date")).startswith(month_str):
                status = str(r.get("Status"))
                if status == "Present":
                    present_days += 1
                    e = float(r.get("Daily_Earnings") or 0)
                    if e > daily_base:
                        total_extra_bonus += (e - daily_base)
                    elif e < daily_base:
                        total_shortfall += (daily_base - e)

        # 2. Update or Create Row in Monthly_Payroll
        # Fetch dynamic base salary
        driver_info = self.sheets.get_driver_by_id(driver_id)
        base_salary = 27000.0
        if driver_info and driver_info.get("Base_Salary"):
            try:
                base_salary = float(driver_info["Base_Salary"])
            except (ValueError, TypeError):
                pass
        
        daily_base = base_salary / 26.0
        
        p_records = payroll_ws.get_all_records()
        row_idx = -1
        for i, pr in enumerate(p_records, start=2):
            if str(pr.get("DriverID")) == str(driver_id) and str(pr.get("Month")) == month_str:
                row_idx = i
                break
        
        working_days = 26
        # Net Payout = (Base / 26 * Present) + Bonus - Shortfall
        net_payout = (daily_base * present_days) + total_extra_bonus - total_shortfall

        row_data = [
            month_str,
            driver_id,
            base_salary,
            working_days,
            present_days,
            0, # Holidays (Admin)
            0, # Sick/LOP (Admin)
            round(total_extra_bonus, 2),
            round(total_shortfall, 2),
            round(max(0, net_payout), 2)
        ]

        if row_idx != -1:
            payroll_ws.update(values=[row_data], range_name=f"A{row_idx}:J{row_idx}")
        else:
            payroll_ws.append_row(row_data)

    def generate_monthly_payroll(self, month_str: str) -> bool:
        """Aggregates attendance data into Monthly_Payroll sheet for a given month (YYYY-MM)"""
        attendance_ws = self.sheets.get_sheet("Attendance")
        payroll_ws = self.sheets.get_sheet("Monthly_Payroll")
        if not attendance_ws or not payroll_ws:
            return False

        records = attendance_ws.get_all_records()
        # Aggregator map: {driver_id: {present: X, earnings: Y, base: 27000}}
        stats: dict[str, Any] = {}
        
        for r in records:
            date = str(r.get("Date"))
            if date.startswith(month_str):
                d_id = str(r.get("DriverID"))
                if d_id not in stats:
                    stats[d_id] = {
                        "present": 0,
                        "total_earnings": 0.0,
                        "base_salary": 27000.0,
                        "extra_bonus": 0.0,
                        "shortfall": 0.0
                    }
                
                status = str(r.get("Status"))
                if status == "Present":
                    stats[d_id]["present"] += 1
                    
                    earnings = float(r.get("Daily_Earnings") or 0)
                    daily_base = 1038.5
                    
                    if earnings > daily_base:
                        stats[d_id]["extra_bonus"] += (earnings - daily_base)
                        stats[d_id]["total_earnings"] += daily_base # Keep base separate
                    elif earnings < daily_base:
                        stats[d_id]["shortfall"] += (daily_base - earnings)
                        stats[d_id]["total_earnings"] += earnings
                    else:
                        stats[d_id]["total_earnings"] += daily_base

        # Push to Payroll sheet
        for d_id, data in stats.items():
            # Calculate working days (approx 26)
            working_days = 26
            net_payout = data["base_salary"] - ( (working_days - data["present"]) * 1038.5 ) + data["extra_bonus"] - data["shortfall"]
            
            # Month, DriverID, Base_Salary, Working_Days, Present_Days, Holidays, Sick_LOP_Days, Extra_Trips_Bonus, Shortfall_Deduction, Net_Payout
            payroll_ws.append_row([
                month_str,
                d_id,
                data["base_salary"],
                working_days,
                data["present"],
                0, # Holidays to be entered by Admin
                0, # Sick/LOP to be entered by Admin
                round(data["extra_bonus"], 2),
                round(data["shortfall"], 2),
                round(max(0, net_payout), 2)
            ])
        
        return True

    def mark_status(self, driver_id: str | int, status: str, date: str) -> bool:
        """Manually sets the status for a driver on a specific date."""
        sheet = self.sheets.get_sheet("Attendance")
        if not sheet:
            return False

        records = sheet.get_all_records()
        row_idx = -1
        for i, r in enumerate(records, start=2):
            if str(r.get("DriverID")) == str(driver_id) and str(r.get("Date")) == date:
                row_idx = i
                break
        
        # Earnings logic for Sick/Holiday/Absent
        earnings = 0.0
        if status == "Present":
            # If we mark as present manually, we assume base daily
            d_info = self.sheets.get_driver_by_id(driver_id)
            base = 27000.0
            if d_info and d_info.get("Base_Salary"):
                base = float(d_info["Base_Salary"])
            earnings = base / 26.0

        if row_idx != -1:
            sheet.update_cell(row_idx, 6, status) # Column 6: Status
            sheet.update_cell(row_idx, 11, earnings) # Column 11: Daily_Earnings
        else:
            # Append new row
            sheet.append_row([
                date,
                driver_id,
                "N/A", # ClientID
                "00:00:00", # Start
                "00:00:00", # End
                status,
                "N/A", # Target_Type
                0,     # Target_Value
                0,     # Completed_Value
                "N/A", # Target_Achieved
                earnings
            ])
        
        # Trigger live payroll update
        self.update_monthly_payroll_live(driver_id, date[:7], earnings)
        return True
