import logging
import uuid
from datetime import datetime
import calendar
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from core.states import (
    BULK_START_ODO,
    BULK_START_IMAGE,
    BULK_END_ODO,
    BULK_END_IMAGE,
    BULK_TRIP_COUNT,
    BULK_FUEL_DATA,
    BULK_FUEL_COST,
    BULK_FUEL_IMAGE,
    BULK_EXPENSES,
    BULK_TOLL_IMAGE,
    BULK_SUMMARY
)
from handlers.base import BaseHandler
from utils.ui import get_main_menu

logger = logging.getLogger(__name__)

class BulkHandler(BaseHandler):
    def _add_to_history(self, context: ContextTypes.DEFAULT_TYPE, state: int) -> None:
        if context.user_data is None: return
        if "bulk_history" not in context.user_data:
            context.user_data["bulk_history"] = []
        context.user_data["bulk_history"].append(state)

    async def handle_back(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.effective_message or context.user_data is None: return None
        history = context.user_data.get("bulk_history", [])
        if not history:
            await update.effective_message.reply_text("Cannot go back further.")
            return None
        
        # Remove current and get previous
        history.pop() # Current
        if not history:
            return await self.start_bulk_day(update, context) if "bulk_end_odo" not in context.user_data else await self.end_bulk_day_cmd(update, context)
            
        prev_state = history.pop()
        # Route based on prev_state
        state_map = {
            BULK_START_ODO: self.start_bulk_day,
            BULK_END_ODO: self.end_bulk_day_cmd,
            BULK_TRIP_COUNT: self.handle_end_image, # Approximation
            BULK_FUEL_DATA: self.handle_trip_count,
            BULK_FUEL_COST: self.handle_fuel_data,
            BULK_EXPENSES: self.handle_fuel_image,
        }
        
        handler = state_map.get(prev_state)
        if handler:
            return await handler(update, context)
        return ConversationHandler.END

    def get_back_keyboard(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="bulk_back"), InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])

    async def start_bulk_day(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.effective_user or not update.effective_message or context.user_data is None: return None
        if context.user_data.get("bulk_session"):
            await update.effective_message.reply_text("⚠️ Active session exists. Use **End Bulk Day**.")
            return ConversationHandler.END

        self._add_to_history(context, BULK_START_ODO)
        driver_id = update.effective_user.id
        stats = self.sheets.get_driver_financial_summary(driver_id)
        
        greeting = (
            f"👋 **Hello, {update.effective_user.first_name}!**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 **Daily Goal**: `0 / 5 Trips`\n"
            f"📈 **Monthly**: `{stats.get('monthly_trips', 0)} / {stats.get('monthly_target_trips', 130)}`\n"
            f"💰 **Earnings**: `₹{stats.get('monthly', 0)} / ₹27k`\n\n"
            "Select vehicle to start:"
        )

        vehicles = self.sheets.get_all_vehicles()
        keyboard = [[InlineKeyboardButton(v["plate"], callback_data=f"bveh_{v['id']}")] for v in vehicles]
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])

        await update.effective_message.reply_text(greeting, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return BULK_START_ODO

    async def handle_start_vehicle(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        query = update.callback_query
        if not query or not query.data or context.user_data is None: return None
        await query.answer()
        
        veh_id = query.data.replace("bveh_", "")
        context.user_data["bulk_vehicle"] = veh_id
        last_odo = self.sheets.get_vehicle_last_odo(veh_id)
        v_map = self.sheets.get_vehicle_map()
        plate = v_map.get(veh_id, veh_id)
        
        await query.edit_message_text(
            f"🚗 Vehicle: **{plate}**\n📟 Last Reading: `{last_odo} km`\n\n"
            "🔢 Enter **Starting Odometer** reading:",
            parse_mode="Markdown"
        )
        return BULK_START_ODO

    async def handle_start_odo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.message or not update.message.text or context.user_data is None: return None
        try:
            odo = float(update.message.text)
            context.user_data["bulk_start_odo"] = odo
            self._add_to_history(context, BULK_START_IMAGE)
            await update.message.reply_text("📸 Please send a photo of the **Starting Odometer**:", reply_markup=self.get_back_keyboard())
            return BULK_START_IMAGE
        except ValueError:
            await update.message.reply_text("Enter a valid number.")
            return BULK_START_ODO

    async def handle_start_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.message or not update.message.photo or not update.effective_user or context.user_data is None: return None
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        content = await file.download_as_bytearray()
        url = self.drive.upload_file(bytes(content), str(update.effective_user.first_name), f"morn_{datetime.now().strftime('%H%M')}", "odo_start")
        context.user_data["bulk_start_image"] = url
        context.user_data["bulk_session"] = True
        context.user_data["bulk_date"] = datetime.now().strftime("%Y-%m-%d")
        
        await update.message.reply_text("✅ **Morning Check-in Successful!**\n\n🌃 Use **End Bulk Day** in the evening.", reply_markup=get_main_menu(self.is_admin(update.effective_user.id)))
        return ConversationHandler.END

    async def end_bulk_day_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.effective_user or not update.effective_message or context.user_data is None: return None
        if not context.user_data.get("bulk_session"):
            await update.effective_message.reply_text("⚠️ No active session.")
            return ConversationHandler.END

        self._add_to_history(context, BULK_END_ODO)
        await update.effective_message.reply_text(f"🌆 **Evening, {update.effective_user.first_name}!**\n🔢 Enter **Ending Odometer** reading:", parse_mode="Markdown")
        return BULK_END_ODO

    async def handle_end_odo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.message or not update.message.text or context.user_data is None: return None
        try:
            odo = float(update.message.text)
            context.user_data["bulk_end_odo"] = odo
            self._add_to_history(context, BULK_END_IMAGE)
            await update.message.reply_text("📸 Send a photo of the **Ending Odometer**:", reply_markup=self.get_back_keyboard())
            return BULK_END_IMAGE
        except ValueError:
            await update.message.reply_text("Invalid number.")
            return BULK_END_ODO

    async def handle_end_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.message or not update.message.photo or not update.effective_user or context.user_data is None: return None
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        content = await file.download_as_bytearray()
        url = self.drive.upload_file(bytes(content), str(update.effective_user.first_name), f"eve_{datetime.now().strftime('%H%M')}", "odo_end")
        context.user_data["bulk_end_image"] = url
        self._add_to_history(context, BULK_TRIP_COUNT)
        await update.message.reply_text("📦 How many **Total Trips** did you complete today?", reply_markup=self.get_back_keyboard())
        return BULK_TRIP_COUNT

    async def handle_trip_count(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.message or not update.message.text or context.user_data is None: return None
        try:
            count = int(update.message.text)
            context.user_data["bulk_total_trips"] = count
            self._add_to_history(context, BULK_FUEL_DATA)
            await update.message.reply_text("⛽ How many **Liters** filled today? (0 if none):", reply_markup=self.get_back_keyboard())
            return BULK_FUEL_DATA
        except ValueError:
            await update.message.reply_text("Enter a number.")
            return BULK_TRIP_COUNT

    async def handle_fuel_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.message or not update.message.text or context.user_data is None: return None
        try:
            liters = float(update.message.text)
            context.user_data["bulk_fuel_liters"] = liters
            self._add_to_history(context, BULK_FUEL_COST)
            await update.message.reply_text("💰 **Total Fuel Cost**? (0 if none):", reply_markup=self.get_back_keyboard())
            return BULK_FUEL_COST
        except ValueError:
            await update.message.reply_text("Enter a number.")
            return BULK_FUEL_DATA

    async def handle_fuel_cost(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.message or not update.message.text or context.user_data is None: return None
        try:
            cost = float(update.message.text)
            context.user_data["bulk_fuel_cost"] = cost
            if cost > 0:
                self._add_to_history(context, BULK_FUEL_IMAGE)
                await update.message.reply_text("📸 Upload **Fuel Receipt**:", reply_markup=self.get_back_keyboard())
                return BULK_FUEL_IMAGE
            else:
                self._add_to_history(context, BULK_EXPENSES)
                await update.message.reply_text("💸 Any **Other Expenses**? (0 if none):", reply_markup=self.get_back_keyboard())
                return BULK_EXPENSES
        except ValueError:
            await update.message.reply_text("Enter a number.")
            return BULK_FUEL_COST

    async def handle_fuel_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.message or not update.message.photo or not update.effective_user or context.user_data is None: return None
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        content = await file.download_as_bytearray()
        url = self.drive.upload_file(bytes(content), str(update.effective_user.first_name), f"fuel_{datetime.now().strftime('%H%M')}", "fuel_receipt")
        context.user_data["bulk_fuel_image"] = url
        self._add_to_history(context, BULK_EXPENSES)
        await update.message.reply_text("💸 Any **Other Expenses**? (0 if none):", reply_markup=self.get_back_keyboard())
        return BULK_EXPENSES

    async def handle_expenses(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.message or not update.message.text or context.user_data is None: return None
        try:
            cost = float(update.message.text)
            context.user_data["bulk_other_expenses"] = cost
            if cost > 0:
                self._add_to_history(context, BULK_TOLL_IMAGE)
                await update.message.reply_text("📸 Upload **Expense Receipt**:", reply_markup=self.get_back_keyboard())
                return BULK_TOLL_IMAGE
            else:
                return await self.show_bulk_summary(update, context)
        except ValueError:
            await update.message.reply_text("Enter a number.")
            return BULK_EXPENSES

    async def handle_toll_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.message or not update.message.photo or not update.effective_user or context.user_data is None: return None
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        content = await file.download_as_bytearray()
        url = self.drive.upload_file(bytes(content), str(update.effective_user.first_name), f"exp_{datetime.now().strftime('%H%M')}", "exp_receipt")
        context.user_data["bulk_other_image"] = url
        return await self.show_bulk_summary(update, context)

    async def show_bulk_summary(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.effective_message or context.user_data is None: return None
        start, end = float(context.user_data.get("bulk_start_odo", 0)), float(context.user_data.get("bulk_end_odo", 0))
        dist = end - start
        liters = float(context.user_data.get("bulk_fuel_liters", 0))
        mileage = round(dist / liters, 2) if liters > 0 else 0
        
        # Sanity Check
        warning = ""
        if dist > 500: warning = "⚠️ **High Distance Detected!** Please verify ODO readings.\n\n"
        if dist < 0: warning = "❌ **Error: Negative Distance!** Please fix ODO readings.\n\n"

        text = (
            f"{warning}📝 **Daily Bulk Summary**\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🛣 Distance: `{dist} KM`\n"
            f"📦 Trips: `{context.user_data.get('bulk_total_trips')}`\n"
            f"📉 **Mileage**: `{mileage} km/l`\n"
            f"💰 Fuel: `₹{context.user_data.get('bulk_fuel_cost')}`\n"
            f"💸 Other: `₹{context.user_data.get('bulk_other_expenses')}`\n\n"
            "Submit to ledger?"
        )
        keyboard = [[InlineKeyboardButton("✅ Confirm", callback_data="bulk_confirm")], [InlineKeyboardButton("⬅️ Edit / Back", callback_data="bulk_back")], [InlineKeyboardButton("🗑️ Discard", callback_data="bulk_discard")]]
        await update.effective_message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return BULK_SUMMARY

    async def handle_bulk_summary(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        query = update.callback_query
        if not query or not query.data or context.user_data is None: return None
        await query.answer()
        if query.data == "bulk_confirm":
            await query.edit_message_text("🚀 Submitting...")
            await self.process_bulk_submission(update, context)
        elif query.data == "bulk_back":
            return await self.handle_back(update, context)
        else:
            await query.edit_message_text("🗑️ Discarded.")
            self._clear_bulk_data(context)
        return ConversationHandler.END

    async def process_bulk_submission(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_user or context.user_data is None: return
        data = context.user_data
        count = int(data.get("bulk_total_trips", 1))
        dist_total = float(data.get("bulk_end_odo", 0)) - float(data.get("bulk_start_odo", 0))
        dist_per_trip = round(dist_total / count, 2)
        d_info = self.sheets.get_driver_by_id(update.effective_user.id)
        c_id = str(d_info.get("ClientID", "C-XGAT")) if d_info else "C-XGAT"
        rates = self.sheets.get_client_rates(c_id)
        trip_records = []
        current_odo = float(data.get("bulk_start_odo", 0))
        for i in range(count):
            next_odo = current_odo + dist_per_trip
            fuel, liters, other = (float(data.get("bulk_fuel_cost", 0)), float(data.get("bulk_fuel_liters", 0)), float(data.get("bulk_other_expenses", 0))) if i == count - 1 else (0,0,0)
            record = { "trip_id": f"B{str(uuid.uuid4())[:7]}", "date": data.get("bulk_date"), "trip_type": "Bulk", "client_name": rates["client_name"], "client_id": c_id, "driver_id": update.effective_user.id, "vehicle_id": data.get("bulk_vehicle"), "start_time": "09:00:00" if i == 0 else "12:00:00", "end_time": "18:00:00" if i == count - 1 else "14:00:00", "start_odo": current_odo, "end_odo": next_odo, "distance": dist_per_trip, "fuel_liters": liters, "fuel_cost": fuel, "other_expenses": other, "client_billed": rates["client_billed"], "driver_payout": rates["driver_payout"], "start_image": data.get("bulk_start_image"), "end_image": data.get("bulk_end_image"), "fuel_image": data.get("bulk_fuel_image") if i == count - 1 else None, "expense_image": data.get("bulk_other_image") if i == count - 1 else None, "remarks": "Daily Bulk Entry" }
            trip_records.append(record)
            current_odo = next_odo
        self.sheets.record_trips_batch(trip_records)
        self.attendance.update_attendance_progress_batch(update.effective_user.id, float(count))
        self.sheets.update_vehicle_status(str(data.get("bulk_vehicle")), float(data.get("bulk_end_odo", 0)), "Idle")
        stats = self.sheets.get_driver_financial_summary(update.effective_user.id)
        if update.effective_message:
            await update.effective_message.reply_text(f"✅ **Daily Ledger Updated!**\nRecorded {count} trips.\n💰 Today: `₹{stats.get('today', 0)}`\n📈 Monthly: `{stats.get('monthly_trips', 0)} / {stats.get('monthly_target_trips', 130)}`", reply_markup=get_main_menu(self.is_admin(update.effective_user.id)), parse_mode="Markdown")
        self._clear_bulk_data(context)

    def _clear_bulk_data(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        if context.user_data is None: return
        for k in ["bulk_session", "bulk_vehicle", "bulk_start_odo", "bulk_start_image", "bulk_end_odo", "bulk_end_image", "bulk_total_trips", "bulk_fuel_liters", "bulk_fuel_cost", "bulk_fuel_image", "bulk_other_expenses", "bulk_other_image", "bulk_date", "bulk_last_known_odo", "bulk_history"]:
            context.user_data.pop(k, None)
