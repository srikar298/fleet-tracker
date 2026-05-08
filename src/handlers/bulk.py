import logging
import uuid
from datetime import datetime
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from core.states import (
    BULK_START_ODO,
    BULK_START_IMAGE,
    BULK_END_ODO,
    BULK_END_IMAGE,
    BULK_TRIP_COUNT,
    BULK_TRIP_CLIENT,
    BULK_TRIP_DETAILS,
    BULK_FUEL_DATA,
    BULK_EXPENSES,
    BULK_SUMMARY
)
from handlers.base import BaseHandler
from utils.ui import get_main_menu

logger = logging.getLogger(__name__)

class BulkHandler(BaseHandler):
    async def start_bulk_day(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        """Morning check-in for bulk mode."""
        if not update.effective_user or not update.effective_message or context.user_data is None:
            return None

        # Check if already started
        if context.user_data.get("bulk_session"):
            await update.effective_message.reply_text("⚠️ You already have an active daily session. Use /endbulkday in the evening.")
            return ConversationHandler.END

        vehicles = self.sheets.get_all_vehicles()
        keyboard = [[InlineKeyboardButton(v["plate"], callback_data=f"bveh_{v['id']}")] for v in vehicles]
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])

        await update.effective_message.reply_text(
            "🌅 **Good Morning!**\nSelect your vehicle to start the day:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return BULK_START_ODO

    async def handle_start_vehicle(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        query = update.callback_query
        if not query or not query.data or context.user_data is None:
            return None
        await query.answer()
        
        veh_id = query.data.replace("bveh_", "")
        context.user_data["bulk_vehicle"] = veh_id
        
        await query.edit_message_text("🔢 Enter your **Starting Odometer** reading:")
        return BULK_START_ODO

    async def handle_start_odo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.message or not update.message.text or context.user_data is None:
            return None
        
        try:
            odo = float(update.message.text)
            context.user_data["bulk_start_odo"] = odo
            await update.message.reply_text("📸 Please send a photo of the **Starting Odometer**:")
            return BULK_START_IMAGE
        except ValueError:
            await update.message.reply_text("Please enter a valid number for odometer.")
            return BULK_START_ODO

    async def handle_start_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.message or not update.message.photo or not update.effective_user or context.user_data is None:
            return None
        
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        content = await file.download_as_bytearray()
        
        url = self.drive.upload_file(
            bytes(content), 
            str(update.effective_user.first_name), 
            f"morning_{datetime.now().strftime('%H%M')}", 
            "odo_start"
        )
        context.user_data["bulk_start_image"] = url
        context.user_data["bulk_session"] = True
        context.user_data["bulk_date"] = datetime.now().strftime("%Y-%m-%d")
        
        await update.message.reply_text(
            "✅ **Morning Check-in Successful!**\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "I've recorded your starting stats. Have a safe day on the road!\n\n"
            "🌃 In the evening, use **/endbulkday** to submit all your trips.",
            parse_mode="Markdown",
            reply_markup=get_main_menu(self.is_admin(update.effective_user.id))
        )
        return ConversationHandler.END

    # --- EVENING FLOW ---
    async def end_bulk_day_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        """Evening bulk submission start."""
        if not update.effective_user or not update.effective_message or context.user_data is None:
            return None

        if not context.user_data.get("bulk_session"):
            await update.effective_message.reply_text("⚠️ You haven't started a daily session. Use /startbulkday first.")
            return ConversationHandler.END

        await update.effective_message.reply_text("🔢 Enter your **Ending Odometer** reading for today:")
        return BULK_END_ODO

    async def handle_end_odo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.message or not update.message.text or context.user_data is None:
            return None
        
        try:
            odo = float(update.message.text)
            start_odo = float(context.user_data.get("bulk_start_odo", 0))
            if odo < start_odo:
                await update.message.reply_text("⚠️ Ending Odometer cannot be less than Starting Odometer.")
                return BULK_END_ODO
                
            context.user_data["bulk_end_odo"] = odo
            await update.message.reply_text("📸 Please send a photo of the **Ending Odometer**:")
            return BULK_END_IMAGE
        except ValueError:
            await update.message.reply_text("Please enter a valid number.")
            return BULK_END_ODO

    async def handle_end_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.message or not update.message.photo or not update.effective_user or context.user_data is None:
            return None
        
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        content = await file.download_as_bytearray()
        
        url = self.drive.upload_file(
            bytes(content), 
            str(update.effective_user.first_name), 
            f"evening_{datetime.now().strftime('%H%M')}", 
            "odo_end"
        )
        context.user_data["bulk_end_image"] = url
        
        await update.message.reply_text("📦 How many trips did you complete today?")
        return BULK_TRIP_COUNT

    async def handle_trip_count(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.message or not update.message.text or context.user_data is None:
            return None
        
        try:
            count = int(update.message.text)
            if count <= 0:
                await update.message.reply_text("Please enter at least 1 trip.")
                return BULK_TRIP_COUNT
            
            context.user_data["bulk_total_trips"] = count
            context.user_data["bulk_trips_data"] = []
            context.user_data["current_trip_idx"] = 1
            
            return await self.prompt_trip_client(update, context)
        except ValueError:
            await update.message.reply_text("Please enter a valid number.")
            return BULK_TRIP_COUNT

    async def prompt_trip_client(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.effective_message or context.user_data is None:
            return None
        idx = context.user_data["current_trip_idx"]
        clients = self.sheets.get_all_clients()
        
        keyboard = [[InlineKeyboardButton(c["Name"], callback_data=f"bcli_{c['ID']}")] for c in clients]
        
        await update.effective_message.reply_text(
            f"🏢 **Trip {idx}**: Select the Client/Vendor:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return BULK_TRIP_CLIENT

    async def handle_trip_client(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        query = update.callback_query
        if not query or not query.data or context.user_data is None:
            return None
        await query.answer()
        
        client_id = query.data.replace("bcli_", "")
        context.user_data["current_client_id"] = client_id
        
        idx = context.user_data["current_trip_idx"]
        await query.edit_message_text(f"🛣 Enter the **Distance (KM)** for Trip {idx}:")
        return BULK_TRIP_DETAILS

    async def handle_trip_details(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.message or not update.message.text or context.user_data is None:
            return None
        
        try:
            val = float(update.message.text)
            idx = int(context.user_data.get("current_trip_idx", 1))
            total = int(context.user_data.get("bulk_total_trips", 1))
            
            # Save this trip
            trips = context.user_data.get("bulk_trips_data", [])
            trips.append({
                "client_id": context.user_data["current_client_id"],
                "value": val
            })
            context.user_data["bulk_trips_data"] = trips
            
            if idx < total:
                context.user_data["current_trip_idx"] = idx + 1
                return await self.prompt_trip_client(update, context)
            else:
                await update.message.reply_text("⛽ Enter total **Fuel Cost** for today (enter 0 if none):")
                return BULK_FUEL_DATA
        except ValueError:
            await update.message.reply_text("Please enter a valid number.")
            return BULK_TRIP_DETAILS

    async def handle_fuel_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.message or not update.message.text or context.user_data is None:
            return None
        
        try:
            cost = float(update.message.text)
            context.user_data["bulk_fuel_cost"] = cost
            await update.message.reply_text("💸 Enter any **Other Expenses** (Tolls, Parking, etc. Enter 0 if none):")
            return BULK_EXPENSES
        except ValueError:
            await update.message.reply_text("Please enter a valid number.")
            return BULK_FUEL_DATA

    async def handle_expenses(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.message or not update.message.text or context.user_data is None:
            return None
        
        try:
            cost = float(update.message.text)
            context.user_data["bulk_other_expenses"] = cost
            
            return await self.show_bulk_summary(update, context)
        except ValueError:
            await update.message.reply_text("Please enter a valid number.")
            return BULK_EXPENSES

    async def show_bulk_summary(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.effective_message or context.user_data is None:
            return None
        
        trips = context.user_data.get("bulk_trips_data", [])
        total_dist = sum(float(t.get("value", 0)) for t in trips)
        
        text = (
            "📝 **Daily Bulk Summary**\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🚗 Vehicle: `{context.user_data.get('bulk_vehicle')}`\n"
            f"🛣 Total Distance: `{total_dist} KM`\n"
            f"📦 Total Trips: `{len(trips)}`\n"
            f"⛽ Fuel: `₹{context.user_data.get('bulk_fuel_cost')}`\n"
            f"💸 Expenses: `₹{context.user_data.get('bulk_other_expenses')}`\n\n"
            "Submit all records to the ledger?"
        )
        
        keyboard = [
            [InlineKeyboardButton("✅ Confirm & Submit", callback_data="bulk_confirm")],
            [InlineKeyboardButton("❌ Discard", callback_data="bulk_discard")]
        ]
        
        await update.effective_message.reply_text(
            text, 
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return BULK_SUMMARY

    async def handle_bulk_summary(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        query = update.callback_query
        if not query or not query.data or context.user_data is None:
            return None
        await query.answer()
        
        if query.data == "bulk_confirm":
            await query.edit_message_text("🚀 Processing daily bulk submission...")
            await self.process_bulk_submission(update, context)
        else:
            await query.edit_message_text("🗑️ Daily session discarded.")
            self._clear_bulk_data(context)
            
        return ConversationHandler.END

    async def process_bulk_submission(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_user or not update.effective_message or context.user_data is None:
            return
        
        data = context.user_data
        trips = data.get("bulk_trips_data", [])
        date = data.get("bulk_date", datetime.now().strftime("%Y-%m-%d"))
        start_odo = float(data.get("bulk_start_odo", 0))
        
        current_odo = start_odo
        
        for i, trip in enumerate(trips):
            rates = self.sheets.get_client_rates(trip["client_id"])
            dist = float(trip.get("value", 0))
            next_odo = current_odo + dist
            
            fuel = float(data.get("bulk_fuel_cost", 0)) if i == len(trips) - 1 else 0
            other = float(data.get("bulk_other_expenses", 0)) if i == len(trips) - 1 else 0
            
            record = {
                "trip_id": f"B{str(uuid.uuid4())[:7]}",
                "date": date,
                "client_name": rates["client_name"],
                "client_id": trip["client_id"],
                "driver_id": update.effective_user.id,
                "vehicle_id": data.get("bulk_vehicle", "Unknown"),
                "start_time": "09:00:00" if i == 0 else "12:00:00", 
                "end_time": "18:00:00" if i == len(trips)-1 else "14:00:00",
                "start_odo": current_odo,
                "end_odo": next_odo,
                "distance": "=M{row}-L{row}",
                "fuel_cost": fuel,
                "other_expenses": other,
                "client_billed": rates["client_billed"],
                "driver_payout": rates["driver_payout"],
                "start_image": data.get("bulk_start_image"),
                "end_image": data.get("bulk_end_image"),
                "remarks": "Daily Bulk Entry"
            }
            
            self.sheets.record_trip(record)
            self.attendance.update_attendance_progress(update.effective_user.id, 1.0)
            current_odo = next_odo

        self.sheets.update_vehicle_status(str(data.get("bulk_vehicle", "Unknown")), float(data.get("bulk_end_odo", 0)), "Idle")
        
        await update.effective_message.reply_text(
            f"✅ **Daily Ledger Updated!**\nRecorded {len(trips)} trips successfully.",
            reply_markup=get_main_menu(self.is_admin(update.effective_user.id))
        )
        self._clear_bulk_data(context)

    def _clear_bulk_data(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        if context.user_data is None:
            return
        keys = [
            "bulk_session", "bulk_vehicle", "bulk_start_odo", "bulk_start_image",
            "bulk_end_odo", "bulk_end_image", "bulk_total_trips", "bulk_trips_data",
            "current_trip_idx", "current_client_id", "bulk_fuel_cost", "bulk_other_expenses",
            "bulk_date"
        ]
        for k in keys:
            context.user_data.pop(k, None)
