import uuid
from datetime import datetime
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from core.gamification import GamificationEngine
from core.validators import TripValidator
from core.states import *
from handlers.base import BaseHandler
from utils.ui import get_main_menu

logger = logging.getLogger(__name__)

class TripHandler(BaseHandler):
    # --- START TRIP FLOW ---
    async def start_trip_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if context.user_data.get("active_trip"):
            await update.effective_message.reply_text("⚠️ You already have an active trip. End it first.")
            return ConversationHandler.END
            
        target = self.attendance.get_daily_target(update.effective_user.id)
        if not target:
            keyboard = [[InlineKeyboardButton("🚗 Trips", callback_data="tgt_Trips"), InlineKeyboardButton("💰 Revenue", callback_data="tgt_Revenue")]]
            await update.message.reply_text(
                f"Good morning, {update.effective_user.first_name}! ☀️\nWhat is your goal for today?",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return DAILY_TARGET_TYPE
            
        return await self.prompt_vehicle_selection(update, context)

    async def handle_target_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        tgt_type = query.data.replace("tgt_", "")
        context.user_data["target_type"] = tgt_type
        
        await query.edit_message_text(f"Awesome! Enter your target number for {tgt_type}:")
        return DAILY_TARGET_VALUE

    async def handle_target_value(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            val = float(update.message.text)
            tgt_type = context.user_data.get("target_type", "Trips")
            self.attendance.set_daily_target(update.effective_user.id, "V-MASTER", tgt_type, val)
            
            await update.message.reply_text(f"🎯 Target set: {val} {tgt_type}. Let's crush it!")
            return await self.prompt_vehicle_selection(update, context)
        except ValueError:
            await update.message.reply_text("Please enter a valid number.")
            return DAILY_TARGET_VALUE

    async def prompt_vehicle_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        vehicles = self.sheets.get_all_vehicles()
        keyboard = [[InlineKeyboardButton(v, callback_data=f"veh_{v}")] for v in vehicles]
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
        
        text = "Select Vehicle:"
        if hasattr(update, "message") and update.message:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.callback_query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return START_TRIP_VEHICLE

    async def handle_start_vehicle(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        if query.data == "cancel":
            await query.edit_message_text("Trip cancelled.")
            return ConversationHandler.END
            
        vehicle_id = query.data.replace("veh_", "")
        context.user_data["vehicle_id"] = vehicle_id
        last_odo = self.sheets.get_vehicle_last_odo(vehicle_id)
        context.user_data["last_odo"] = last_odo
        
        await query.edit_message_text(f"Vehicle: {vehicle_id}\nLast Reading: {last_odo} km\n\nWhere are you going? (Enter Route/Client):")
        return START_TRIP_DEST

    async def handle_start_dest(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data["destination"] = update.message.text
        last = context.user_data.get("last_odo", 0)
        await update.message.reply_text(f"Enter CURRENT Odometer reading (Last: {last} km):")
        return START_TRIP_ODO

    async def handle_start_odo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            odo = float(update.message.text)
            context.user_data["start_odo"] = odo
            
            last_odo = context.user_data.get("last_odo", 0)
            if odo < last_odo:
                await update.message.reply_text(f"❌ Entered KM ({odo}) is less than last trip ({last_odo}). Please recheck:")
                return START_TRIP_ODO
            elif odo - last_odo > 300:
                await update.message.reply_text("⚠️ Large jump detected (>300km). We have flagged this for review.\n\nPlease upload a PHOTO of the start odometer:")
            else:
                await update.message.reply_text("Please upload a PHOTO of the start odometer:")
            return START_TRIP_IMAGE
        except ValueError:
            await update.message.reply_text("Invalid number. Please enter digits only.")
            return START_TRIP_ODO

    async def handle_start_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        
        driver_name = update.effective_user.first_name
        trip_id = context.user_data.setdefault("trip_id", str(uuid.uuid4())[:8])
        url = self.drive.upload_file(photo_bytes, driver_name, trip_id, "start_odo")
        context.user_data["start_image_url"] = url
            
        await update.message.reply_text("Share your CURRENT LOCATION (📎 -> Location):")
        return START_TRIP_LOC

    async def handle_start_loc(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        loc = update.message.location
        if loc:
            context.user_data["start_location"] = f"https://maps.google.com/?q={loc.latitude},{loc.longitude}"
        else:
            context.user_data["start_location"] = "Manual: " + update.message.text
            
        context.user_data["start_time"] = datetime.now()
        context.user_data["active_trip"] = True
        
        self.attendance.log_activity(update.effective_user.id, "V-MASTER") 
        self.sheets.update_vehicle_status(context.user_data['vehicle_id'], context.user_data['start_odo'], "On Trip")
        
        await update.message.reply_text(
            f"Trip STARTED ✅\nVehicle: {context.user_data['vehicle_id']}\n"
            f"Start KM: {context.user_data['start_odo']}\n"
            f"Time: {context.user_data['start_time'].strftime('%I:%M %p')}\n\n"
            "Drive safe!", reply_markup=get_main_menu()
        )
        return ConversationHandler.END

    # --- END TRIP FLOW ---
    async def end_trip_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.user_data.get("active_trip") and "vehicle_id" not in context.user_data:
            vehicles = self.sheets.get_all_vehicles()
            keyboard = [[InlineKeyboardButton(v, callback_data=f"veh_{v}")] for v in vehicles]
            keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
            await update.message.reply_text("Which vehicle are you ending the trip for?", reply_markup=InlineKeyboardMarkup(keyboard))
            return END_TRIP_VEHICLE
            
        v_id = context.user_data.get("vehicle_id", "Unknown")
        await update.message.reply_text(f"Ending trip for {v_id}. Enter END Odometer:")
        return END_TRIP_ODO

    async def handle_end_vehicle(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        if query.data == "cancel":
            await query.edit_message_text("Cancelled.")
            return ConversationHandler.END
            
        context.user_data["vehicle_id"] = query.data.replace("veh_", "")
        await query.edit_message_text(f"Ending trip for {context.user_data['vehicle_id']}. Enter END Odometer:")
        return END_TRIP_ODO

    async def handle_end_odo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            odo = float(update.message.text)
            context.user_data["end_odo"] = odo
            await update.message.reply_text("Upload a PHOTO of the end odometer:")
            return END_TRIP_IMAGE
        except ValueError:
            await update.message.reply_text("Invalid number.")
            return END_TRIP_ODO

    async def handle_end_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        
        driver_name = update.effective_user.first_name
        trip_id = context.user_data.setdefault("trip_id", str(uuid.uuid4())[:8])
        url = self.drive.upload_file(photo_bytes, driver_name, trip_id, "end_odo")
        context.user_data["end_image_url"] = url
            
        await update.message.reply_text("Share your END LOCATION (📎 -> Location):")
        return END_TRIP_LOC

    async def handle_end_loc(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        loc = update.message.location
        if loc:
            context.user_data["end_location"] = f"https://maps.google.com/?q={loc.latitude},{loc.longitude}"
        else:
            context.user_data["end_location"] = "Manual: " + update.message.text
            
        context.user_data["end_time"] = datetime.now()
        
        keyboard = [
            [InlineKeyboardButton("✅ Yes", callback_data="fuel_yes"), InlineKeyboardButton("❌ No", callback_data="fuel_no")]
        ]
        await update.message.reply_text(
            "Did you refuel during this trip?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return FUEL_PROMPT

    async def handle_fuel_prompt(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        if query.data == "fuel_yes":
            await query.edit_message_text("Enter Liters and Cost (e.g., '20, 2000'):")
            return FUEL_DATA
        else:
            context.user_data["fuel_liters"] = "0"
            context.user_data["fuel_cost"] = "0"
            await query.edit_message_text("Enter Total Revenue for this trip (in ₹):")
            return END_TRIP_REVENUE

    async def handle_fuel_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        data = update.message.text.split(",")
        liters = data[0].strip()
        cost = data[1].strip() if len(data) > 1 else "0"
        
        context.user_data["fuel_liters"] = liters
        context.user_data["fuel_cost"] = cost
        
        try:
            start = float(context.user_data.get("start_odo", 0))
            if start == 0: start = float(self.sheets.get_vehicle_last_odo(context.user_data.get("vehicle_id")))
            end = float(context.user_data.get("end_odo", 0))
            distance = end - start
            l = float(liters)
            if l > 0:
                mileage = distance / l
                context.user_data["mileage"] = mileage
                await update.message.reply_text(f"⚠️ Your mileage: {mileage:.1f} km/l (Expected: 12-15)")
        except Exception:
            pass
            
        await update.message.reply_text("Upload a photo of the FUEL RECEIPT:")
        return FUEL_IMAGE

    async def handle_fuel_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        
        driver_name = update.effective_user.first_name
        trip_id = context.user_data.setdefault("trip_id", str(uuid.uuid4())[:8])
        url = self.drive.save_fuel_receipt(
            photo_bytes, driver_name, trip_id, 
            context.user_data.get('vehicle_id', 'Unknown'), 
            context.user_data.get("fuel_cost", 0)
        )
        context.user_data["fuel_image_url"] = url
        
        await update.message.reply_text("Enter Total Revenue for this trip (in ₹):")
        return END_TRIP_REVENUE

    async def handle_end_revenue(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            context.user_data["revenue"] = float(update.message.text)
            await update.message.reply_text("Any other expenses? (Toll/Parking/Maintenance)\nEnter total amount (or 0):")
            return END_TRIP_OTHER_EXP
        except ValueError:
            await update.message.reply_text("Invalid number. Try again:")
            return END_TRIP_REVENUE

    async def handle_end_other_exp(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            other = float(update.message.text)
            context.user_data["other_expenses"] = other
            if other > 0:
                await update.message.reply_text("Please upload a photo of the receipt for this expense (Toll/Maintenance):")
                return END_TRIP_EXPENSE_PHOTO
            else:
                return await self.show_end_summary(update, context)
        except ValueError:
            await update.message.reply_text("Invalid number. Try again:")
            return END_TRIP_OTHER_EXP

    async def handle_end_expense_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        
        driver_name = update.effective_user.first_name
        v_id = context.user_data.get("vehicle_id", "Unknown")
        cost = context.user_data.get("other_expenses", 0)
        
        url = self.drive.save_expense_receipt(photo_bytes, driver_name, v_id, cost)
        context.user_data["expense_image_url"] = url
        
        return await self.show_end_summary(update, context)

    async def show_end_summary(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        start = context.user_data.get("start_odo")
        if start is None:
            start = self.sheets.get_vehicle_last_odo(context.user_data.get("vehicle_id", "Unknown"))
            context.user_data["start_odo"] = start
            
        end = context.user_data.get("end_odo", 0)
        distance = end - float(start)
        revenue = context.user_data.get("revenue", 0)
        fuel = float(context.user_data.get("fuel_cost", 0))
        other = context.user_data.get("other_expenses", 0)
        net = revenue - fuel - other
        
        context.user_data["distance"] = distance
        context.user_data["net"] = net
        
        gamification_text = ""
        target = self.attendance.get_daily_target(update.effective_user.id)
        if target and target["value"] > 0:
            summary_stats = self.sheets.get_driver_today_summary(update.effective_user.id)
            current_trips = summary_stats["trips"] + 1
            current_rev = summary_stats["revenue"] + revenue
            
            current_val = current_trips if target["type"] == "Trips" else current_rev
            gamification_text = GamificationEngine.generate_progress_bar(current_val, target["value"], target["type"])
        
        summary = (
            f"📊 *Trip Summary*\n"
            f"Distance: {distance} km\n"
            f"Fuel: ₹{fuel}\n"
            f"Other: ₹{other}\n"
            f"Revenue: ₹{revenue}\n"
            f"------------\n"
            f"Net Profit: ₹{net}\n"
            f"{gamification_text}"
        )
        
        keyboard = [[InlineKeyboardButton("✅ Confirm", callback_data="confirm"), InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
        
        if hasattr(update, "message") and update.message:
            await update.message.reply_text(summary, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.callback_query.message.reply_text(summary, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
            
        return END_TRIP_SUMMARY

    async def handle_end_summary(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        if query.data == "confirm":
            await query.edit_message_text("Saving trip...")
            await self.complete_trip(update, context)
        else:
            await query.edit_message_text("Trip submission cancelled. Data discarded.")
            context.user_data["active_trip"] = False
        return ConversationHandler.END

    async def complete_trip(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            distance = context.user_data.get("distance", 0)
            start_time = context.user_data.get("start_time", datetime.now())
            end_time = context.user_data.get("end_time", datetime.now())
            duration = int((end_time - start_time).total_seconds() / 60)
            
            trip_data = {
                "distance": distance,
                "duration_mins": duration,
                "mileage": context.user_data.get("mileage", 0),
                "fuel_cost": float(context.user_data.get("fuel_cost", 0)),
                "revenue": context.user_data.get("revenue", 0)
            }
            
            validator = TripValidator()
            flags, score = validator.evaluate_trip(trip_data)
            
            trip_id = context.user_data.get("trip_id", str(uuid.uuid4())[:8])
            date = datetime.now().strftime("%Y-%m-%d")
            
            flag_str = ", ".join(flags) if flags else "OK"
            if flag_str != "OK": 
                flag_str = "🚩 " + flag_str
                self.drive.flag_trip_images(date, update.effective_user.first_name, trip_id)
            
            trip_record = {
                "trip_id": trip_id, "date": date, "vendor_id": "V-MASTER",
                "driver_id": update.effective_user.id, "vehicle_id": context.user_data.get("vehicle_id", "Unknown"),
                "start_time": start_time.strftime('%H:%M:%S'), "end_time": end_time.strftime('%H:%M:%S'),
                "duration": duration, "start_location": context.user_data.get("start_location"),
                "end_location": context.user_data.get("end_location"),
                "start_odo": context.user_data.get("start_odo", 0), "end_odo": context.user_data.get("end_odo", 0),
                "distance": "=L{row}-K{row}", "fuel_liters": context.user_data.get("fuel_liters", 0),
                "fuel_cost": context.user_data.get("fuel_cost", 0), "other_expenses": context.user_data.get("other_expenses", 0),
                "revenue": context.user_data.get("revenue", 0), "net_profit": "=Q{row}-O{row}-P{row}",
                "driver_score": score,
                "start_image": context.user_data.get("start_image_url"), "end_image": context.user_data.get("end_image_url"),
                "fuel_image": context.user_data.get("fuel_image_url"),
                "flag": flag_str,
                "remarks": f"Destination: {context.user_data.get('destination', 'None')}"
            }
            
            self.sheets.record_trip(trip_record)
            self.sheets.update_vehicle_status(context.user_data.get('vehicle_id', 'Unknown'), context.user_data.get("end_odo", 0), "Idle")
            
            await update.effective_message.reply_text(f"✅ Trip successfully recorded in the ledger!\nTrip ID: {trip_id}", reply_markup=get_main_menu())
        except Exception as e:
            logger.error(f"Error completing trip: {e}")
            await update.effective_message.reply_text("⚠️ An error occurred while saving the trip. Please contact admin.")
        finally:
            context.user_data["active_trip"] = False
