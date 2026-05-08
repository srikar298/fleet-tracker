import logging
import os
import uuid
from datetime import datetime
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from core.states import (
    DAILY_TARGET_VALUE,
    END_TRIP_EXPENSE_PHOTO,
    END_TRIP_IMAGE,
    END_TRIP_LOC,
    END_TRIP_ODO,
    END_TRIP_OTHER_EXP,
    END_TRIP_REVENUE,
    END_TRIP_SUMMARY,
    END_TRIP_VEHICLE,
    FUEL_DATA,
    FUEL_IMAGE,
    FUEL_PROMPT,
    START_TRIP_IMAGE,
    START_TRIP_LOC,
    START_TRIP_ODO,
    START_TRIP_VEHICLE,
)
from core.validators import TripValidator
from handlers.base import BaseHandler
from utils.ui import get_main_menu

logger = logging.getLogger(__name__)


class TripHandler(BaseHandler):
    # --- START TRIP FLOW ---
    async def start_trip_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.effective_user or not update.effective_message or context.user_data is None:
            return None

        if context.user_data.get("active_trip"):
            await update.effective_message.reply_text("⚠️ You already have an active trip. End it first.")
            return ConversationHandler.END

        target = self.attendance.get_daily_target(update.effective_user.id)
        if not target:
            # Default to 5 Trips as requested
            self.attendance.set_daily_target(
                update.effective_user.id,
                "C-XGAT",
                "Trips",
                5.0,
            )
            await update.effective_message.reply_text(
                f"Good morning, {update.effective_user.first_name}! ☀️\n"
                "Your daily target is set to **5 Trips**. Let's get started!",
                parse_mode="Markdown",
            )

        return await self.prompt_vehicle_selection(update, context)

    async def handle_target_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        query = update.callback_query
        if not query or not query.data or context.user_data is None:
            return None
        await query.answer()
        tgt_type = str(query.data.replace("tgt_", ""))
        context.user_data["target_type"] = tgt_type

        await query.edit_message_text(f"Awesome! Enter your target number for {tgt_type}:")
        return DAILY_TARGET_VALUE

    async def handle_target_value(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.message or not update.message.text or not update.effective_user or context.user_data is None:
            return None
        try:
            val = float(update.message.text)
            tgt_type = str(context.user_data.get("target_type", "Trips"))
            self.attendance.set_daily_target(
                update.effective_user.id,
                "V-MASTER",
                tgt_type,
                val,
            )

            await update.message.reply_text(f"🎯 Target set: {val} {tgt_type}. Let's crush it!")
            return await self.prompt_vehicle_selection(update, context)
        except ValueError:
            await update.message.reply_text("Please enter a valid number.")
            return DAILY_TARGET_VALUE

    async def prompt_vehicle_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.effective_user:
            return None
        vehicles = self.sheets.get_all_vehicles()
        keyboard: list[list[InlineKeyboardButton]] = [
            [InlineKeyboardButton(v["plate"], callback_data=f"veh_{v['id']}")] for v in vehicles
        ]
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])

        text = "Select Vehicle:"

        if update.message:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        elif update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return START_TRIP_VEHICLE

    async def handle_start_vehicle(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        query = update.callback_query
        if not query or not query.data or context.user_data is None:
            return None
        await query.answer()
        if query.data == "cancel":
            await query.edit_message_text("Trip cancelled.")
            return ConversationHandler.END

        vehicle_id = str(query.data.replace("veh_", ""))
        context.user_data["vehicle_id"] = vehicle_id
        
        v_map = self.sheets.get_vehicle_map()
        plate = v_map.get(vehicle_id, vehicle_id)
        
        last_odo = self.sheets.get_vehicle_last_odo(vehicle_id)
        context.user_data["last_odo"] = last_odo

        await query.edit_message_text(
            f"Vehicle: **{plate}**\nLast Reading: {last_odo} km\n\nEnter CURRENT Odometer reading:",
            parse_mode="Markdown"
        )
        return START_TRIP_ODO

    async def handle_start_odo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.message or not update.message.text or context.user_data is None:
            return None
        try:
            odo = float(update.message.text)
            context.user_data["start_odo"] = odo

            last_odo = float(context.user_data.get("last_odo", 0))
            if odo < last_odo:
                await update.message.reply_text(
                    f"❌ Entered KM ({odo}) is less than last trip ({last_odo}). Please recheck:"
                )
                return START_TRIP_ODO
            elif odo - last_odo > 300:
                await update.message.reply_text(
                    "⚠️ Large jump detected (>300km). We have flagged this for review.\n\nPlease upload a PHOTO of the start odometer:"
                )
            else:
                await update.message.reply_text("Please upload a PHOTO of the start odometer:")
            return START_TRIP_IMAGE
        except ValueError:
            await update.message.reply_text("Please enter a valid number.")
            return START_TRIP_ODO

    async def handle_start_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.message or not update.message.photo or not update.effective_user or context.user_data is None:
            return None

        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()

        driver_name = str(update.effective_user.first_name)
        trip_id = str(context.user_data.setdefault("trip_id", str(uuid.uuid4())[:8]))
        url = self.drive.upload_file(
            photo_bytes,
            driver_name,
            trip_id,
            "start",
        )
        context.user_data["start_image_url"] = url

        # Use Native Location Request
        keyboard = [[KeyboardButton("📍 Share Current Location", request_location=True)]]
        await update.message.reply_text(
            "Perfect! Now tap the button below to share your **Live Pickup Location**:",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
        )
        return START_TRIP_LOC

    async def handle_start_loc(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.message or not update.message.location or not update.effective_user or context.user_data is None:
            return None
        location = update.message.location

        loc_str = f"{location.latitude}, {location.longitude}"
        context.user_data["start_location"] = loc_str

        context.user_data["start_time"] = datetime.now()
        context.user_data["active_trip"] = True

        self.attendance.log_activity(update.effective_user.id, "C-XGAT")
        self.sheets.update_vehicle_status(
            str(context.user_data["vehicle_id"]),
            context.user_data["start_odo"],
            "On Trip",
        )

        is_admin = self.is_admin(update.effective_user.id)
        await update.message.reply_text(
            "✅ Location Verified! Drive safe. Trip has started.", reply_markup=get_main_menu(is_admin)
        )
        return ConversationHandler.END

    # --- END TRIP FLOW ---
    async def end_trip_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.message or not update.effective_user or context.user_data is None:
            return None
        if not context.user_data.get("active_trip"):
            await update.message.reply_text("⚠️ You don't have an active trip to end.")
            return ConversationHandler.END

        # Auto-detect vehicle_id from active trip
        v_id = context.user_data.get("vehicle_id")
        if v_id:
            v_map = self.sheets.get_vehicle_map()
            plate = v_map.get(str(v_id), str(v_id))
            context.user_data["vehicle_id"] = v_id
            await update.message.reply_text(f"🏁 Ending trip for vehicle: **{plate}**", parse_mode="Markdown")
            await update.message.reply_text("Enter current ODOMETER reading:")
            return END_TRIP_ODO

        # Fallback if vehicle_id was lost (unlikely with persistence)
        vehicles = self.sheets.get_all_vehicles()
        keyboard: list[list[InlineKeyboardButton]] = [
            [InlineKeyboardButton(v["plate"], callback_data=f"endveh_{v['id']}")] for v in vehicles
        ]
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
        await update.message.reply_text(
            "Which vehicle are you ending the trip for?",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return END_TRIP_VEHICLE

    async def handle_end_vehicle(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        query = update.callback_query
        if not query or not query.data or context.user_data is None:
            return None
        await query.answer()
        if query.data == "cancel":
            await query.edit_message_text("Cancelled.")
            return ConversationHandler.END

        v_id = str(query.data.replace("endveh_", ""))
        context.user_data["vehicle_id"] = v_id
        v_map = self.sheets.get_vehicle_map()
        plate = v_map.get(v_id, v_id)
        await query.edit_message_text(f"Ending trip for {plate}. Enter END Odometer:")
        return END_TRIP_ODO

    async def handle_end_odo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.message or not update.message.text or context.user_data is None:
            return None
        try:
            odo = float(update.message.text)
            start_odo = float(context.user_data.get("start_odo", 0))
            if odo < start_odo:
                await update.message.reply_text(
                    f"❌ End KM ({odo}) cannot be less than Start KM ({start_odo}). Try again:"
                )
                return END_TRIP_ODO

            context.user_data["end_odo"] = odo
            await update.message.reply_text("Please upload a PHOTO of the final odometer:")
            return END_TRIP_IMAGE
        except ValueError:
            await update.message.reply_text("Please enter a valid number.")
            return END_TRIP_ODO

    async def handle_end_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.message or not update.message.photo or not update.effective_user or context.user_data is None:
            return None
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()

        driver_name = str(update.effective_user.first_name)
        trip_id = str(context.user_data.get("trip_id", "Unknown"))
        url = self.drive.upload_file(
            photo_bytes,
            driver_name,
            trip_id,
            "end",
        )
        context.user_data["end_image_url"] = url

        keyboard = [[KeyboardButton("📍 Share Drop-off Location", request_location=True)]]
        await update.message.reply_text(
            "Now share your **Live Drop-off Location**:",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
        )
        return END_TRIP_LOC

    async def handle_end_loc(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.message or not update.message.location or context.user_data is None:
            return None
        location = update.message.location

        loc_str = f"{location.latitude}, {location.longitude}"
        context.user_data["end_location"] = loc_str
        await update.message.reply_text("Location captured! 📍")

        context.user_data["end_time"] = datetime.now()

        keyboard: list[list[InlineKeyboardButton]] = [
            [
                InlineKeyboardButton("✅ Yes", callback_data="fuel_yes"),
                InlineKeyboardButton("❌ No", callback_data="fuel_no"),
            ]
        ]
        await update.message.reply_text(
            "Did you refuel during this trip?",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return FUEL_PROMPT

    async def handle_fuel_prompt(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        query = update.callback_query
        if not query or not query.data or context.user_data is None:
            return None
        await query.answer()
        if query.data == "fuel_yes":
            await query.edit_message_text("Enter Liters and Cost (e.g., '20, 2000'):")
            return FUEL_DATA
        else:
            context.user_data["fuel_liters"] = "0"
            context.user_data["fuel_cost"] = "0"
            await query.edit_message_text("Any other expenses? (Toll/Parking/Maintenance)\nEnter total amount (or 0):")
            return END_TRIP_OTHER_EXP

    async def handle_fuel_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.message or not update.message.text or context.user_data is None:
            return None
        parts = update.message.text.split(",")
        liters = parts[0].strip()
        cost = parts[1].strip() if len(parts) > 1 else "0"

        context.user_data["fuel_liters"] = liters
        context.user_data["fuel_cost"] = cost

        try:
            start = float(context.user_data.get("start_odo", 0))
            if start == 0:
                start = float(self.sheets.get_vehicle_last_odo(str(context.user_data.get("vehicle_id", "Unknown"))))
            end = float(context.user_data.get("end_odo", 0))
            distance = end - start
            liters_val = float(liters)
            if liters_val > 0:
                mileage = distance / liters_val
                context.user_data["mileage"] = mileage
                await update.message.reply_text(f"⚠️ Your mileage: {mileage:.1f} km/l (Expected: 12-15)")
        except Exception:
            pass

        await update.message.reply_text("Upload a photo of the FUEL RECEIPT:")
        return FUEL_IMAGE

    async def handle_fuel_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.message or not update.message.photo or not update.effective_user or context.user_data is None:
            return None
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()

        driver_name = str(update.effective_user.first_name)
        trip_id = str(context.user_data.get("trip_id", str(uuid.uuid4())[:8]))
        url = self.drive.save_fuel_receipt(
            photo_bytes,
            driver_name,
            trip_id,
            str(context.user_data.get("vehicle_id", "Unknown")),
            context.user_data.get("fuel_cost", 0),
        )
        context.user_data["fuel_image_url"] = url

        await update.message.reply_text("Any other expenses? (Toll/Parking/Maintenance)\nEnter total amount (or 0):")
        return END_TRIP_OTHER_EXP

    async def handle_end_other_exp(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.message or not update.message.text or context.user_data is None:
            return None
        try:
            other = float(update.message.text)
            context.user_data["other_expenses"] = other
            if other > 0:
                await update.message.reply_text(
                    "Please upload a photo of the receipt for this expense (Toll/Maintenance):"
                )
                return END_TRIP_EXPENSE_PHOTO
            else:
                return await self.show_end_summary(update, context)
        except ValueError:
            await update.message.reply_text("Invalid number. Try again:")
            return END_TRIP_OTHER_EXP

    async def handle_end_expense_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.message or not update.message.photo or not update.effective_user or context.user_data is None:
            return None
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()

        driver_name = str(update.effective_user.first_name)
        v_id = str(context.user_data.get("vehicle_id", "Unknown"))
        cost = context.user_data.get("other_expenses", 0)
        trip_id = str(context.user_data.get("trip_id", "Unknown"))

        url = self.drive.save_expense_receipt(photo_bytes, driver_name, v_id, cost)
        context.user_data["expense_image_url"] = url

        return await self.show_end_summary(update, context)


    async def show_end_summary(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.effective_message or context.user_data is None:
            return None
        start = context.user_data.get("start_odo")
        if start is None:
            start = self.sheets.get_vehicle_last_odo(str(context.user_data.get("vehicle_id", "Unknown")))
            context.user_data["start_odo"] = start

        end = float(context.user_data.get("end_odo", 0))
        distance = end - float(start)
        fuel = float(context.user_data.get("fuel_cost", 0))
        other = float(context.user_data.get("other_expenses", 0))
        total_expenses = fuel + other

        context.user_data["distance"] = distance
        context.user_data["total_expenses"] = total_expenses

        summary = (
            f"📊 *Trip Summary*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🛣 Distance: `{distance} km`\n"
            f"⛽ Fuel: `₹{fuel}`\n"
            f"🛠 Other: `₹{other}`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 *Total Spent*: `₹{total_expenses}`\n"
        )

        keyboard: list[list[InlineKeyboardButton]] = [
            [
                InlineKeyboardButton("✅ Confirm", callback_data="confirm"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
            ]
        ]

        await update.effective_message.reply_text(
            summary,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return END_TRIP_SUMMARY

    async def handle_end_summary(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        query = update.callback_query
        if not query or not query.data or context.user_data is None:
            return None
        await query.answer()
        if query.data == "confirm":
            await query.edit_message_text("Saving trip...")
            await self.complete_trip(update, context)
        else:
            await query.edit_message_text("Trip submission cancelled. Data discarded.")
            context.user_data["active_trip"] = False
        return ConversationHandler.END

    async def complete_trip(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_user or not update.effective_message or context.user_data is None:
            return
        try:
            distance = float(context.user_data.get("distance", 0))
            start_time = context.user_data.get("start_time", datetime.now())
            end_time = context.user_data.get("end_time", datetime.now())
            duration = int((end_time - start_time).total_seconds() / 60)

            trip_data: dict[str, Any] = {
                "distance": distance,
                "fuel_cost": float(context.user_data.get("fuel_cost", 0)),
            }

            validator = TripValidator()
            flags, score = validator.evaluate_trip(trip_data)

            trip_id = str(context.user_data.get("trip_id", str(uuid.uuid4())[:8]))
            date = datetime.now().strftime("%Y-%m-%d")

            flag_str = ", ".join(flags) if flags else "OK"
            if flag_str != "OK":
                flag_str = "🚩 " + flag_str
                self.drive.flag_trip_images(
                    date,
                    str(update.effective_user.first_name),
                    trip_id,
                )

            # Fetch B2B Rates from Master_Clients
            driver_info = self.sheets.get_driver_by_id(update.effective_user.id)
            client_id = str(driver_info.get("ClientID", "C-XGAT")) if driver_info else "C-XGAT"
            rates = self.sheets.get_client_rates(client_id)

            trip_record: dict[str, Any] = {
                "trip_id": trip_id,
                "date": date,
                "client_name": rates["client_name"],
                "client_id": client_id,
                "driver_id": update.effective_user.id,
                "vehicle_id": context.user_data.get("vehicle_id", "Unknown"),
                "start_time": start_time.strftime("%H:%M:%S"),
                "end_time": end_time.strftime("%H:%M:%S"),
                "duration": duration,
                "start_location": context.user_data.get("start_location"),
                "end_location": context.user_data.get("end_location"),
                "start_odo": context.user_data.get("start_odo", 0),
                "end_odo": context.user_data.get("end_odo", 0),
                "distance": "=M{row}-L{row}",
                "fuel_liters": context.user_data.get("fuel_liters", 0),
                "fuel_cost": context.user_data.get("fuel_cost", 0),
                "other_expenses": context.user_data.get("other_expenses", 0),
                "client_billed": rates["client_billed"],
                "driver_payout": rates["driver_payout"],
                "net_profit": "=R{row}-S{row}-P{row}-Q{row}", # Gross Margin = Billed - Payout - Fuel - Other
                "driver_score": score,
                "start_image": context.user_data.get("start_image_url"),
                "end_image": context.user_data.get("end_image_url"),
                "fuel_image": context.user_data.get("fuel_image_url"),
                "flag": flag_str,
                "remarks": "B2B Trip recorded",
            }

            self.sheets.record_trip(trip_record)
            self.attendance.update_attendance_progress(update.effective_user.id, 1.0)
            self.sheets.update_vehicle_status(
                str(context.user_data.get("vehicle_id", "Unknown")),
                context.user_data.get("end_odo", 0),
                "Idle",
            )

            is_admin = self.is_admin(update.effective_user.id)

            # Milestone Check
            summary = self.sheets.get_driver_today_summary(update.effective_user.id)
            trips_done = summary["trips"]
            target = 5

            # Fetch Financial Summary for Gamification
            fin = self.sheets.get_driver_financial_summary(update.effective_user.id)
            earnings_text = f"\n💰 **Today's Earnings**: `₹{fin['today']}`\n📈 **Monthly Progress**: `₹{fin['monthly']} / ₹{fin['base']}`"

            if trips_done >= target:
                text = (
                    "🏆 *Daily Goal Reached!* 🏆\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    f"That was trip number **{trips_done}** today! Excellent work.\n"
                    f"{earnings_text}\n\n"
                    "You've smashed your target. Do you want to keep going for extra rewards?"
                )
                await update.effective_message.reply_text(
                    text, parse_mode="Markdown", reply_markup=get_main_menu(is_admin)
                )
            else:
                trips_left = target - trips_done
                ordinal = {1: "st", 2: "nd", 3: "rd"}.get(trips_done % 10, "th") if not 11 <= trips_done <= 13 else "th"
                
                text = (
                    "✅ *Trip Recorded!* ✅\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    f"Great job! That was your **{trips_done}{ordinal}** trip today.\n"
                    f"🚀 **{trips_left}** more to go to reach your daily goal of {target}!\n"
                    f"{earnings_text}\n\n"
                    f"_Trip ID: {trip_id}_"
                )
                await update.effective_message.reply_text(
                    text, parse_mode="Markdown", reply_markup=get_main_menu(is_admin)
                )
        except Exception as e:
            logger.error(f"Error completing trip: {e}")
            await update.effective_message.reply_text(
                "⚠️ An error occurred while saving the trip. Please contact admin."
            )
        finally:
            self._clear_trip_data(context)

    def _clear_trip_data(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Resets trip-specific data but keeps vehicle and last odo for carry-over."""
        if context.user_data is None:
            return
        if "end_odo" in context.user_data:
            context.user_data["last_odo"] = context.user_data["end_odo"]

        keys_to_clear = [
            "active_trip",
            "trip_id",
            "start_odo",
            "end_odo",
            "start_image_url",
            "end_image_url",
            "fuel_image_url",
            "expense_image_url",
            "start_location",
            "end_location",
            "fuel_cost",
            "other_expenses",
            "start_time",
            "end_time",
            "distance",
            "net",
        ]
        for key in keys_to_clear:
            context.user_data.pop(key, None)
