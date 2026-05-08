import logging
import uuid
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
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
    async def start_trip_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if context.user_data.get("active_trip"):  # type: ignore
            await update.effective_message.reply_text(  # type: ignore
                "⚠️ You already have an active trip. End it first."
            )
            return ConversationHandler.END

        target = self.attendance.get_daily_target(update.effective_user.id)  # type: ignore
        if not target:
            # Default to 5 Trips as requested
            self.attendance.set_daily_target(
                update.effective_user.id,
                "V-MASTER",
                "Trips",
                5.0,
            )
            await update.message.reply_text(  # type: ignore
                f"Good morning, {update.effective_user.first_name}! ☀️\n"
                "Your daily target is set to **5 Trips**. Let's get started!",
                parse_mode="Markdown",
            )

        return await self.prompt_vehicle_selection(update, context)

    async def handle_target_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()  # type: ignore
        tgt_type = query.data.replace("tgt_", "")  # type: ignore
        context.user_data["target_type"] = tgt_type  # type: ignore

        await query.edit_message_text(  # type: ignore
            f"Awesome! Enter your target number for {tgt_type}:"
        )
        return DAILY_TARGET_VALUE

    async def handle_target_value(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            val = float(update.message.text)  # type: ignore
            tgt_type = context.user_data.get("target_type", "Trips")  # type: ignore
            self.attendance.set_daily_target(
                update.effective_user.id,
                "V-MASTER",
                tgt_type,
                val,  # type: ignore
            )

            await update.message.reply_text(  # type: ignore
                f"🎯 Target set: {val} {tgt_type}. Let's crush it!"
            )
            return await self.prompt_vehicle_selection(update, context)
        except ValueError:
            await update.message.reply_text("Please enter a valid number.")  # type: ignore
            return DAILY_TARGET_VALUE

    async def prompt_vehicle_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        vehicles = self.sheets.get_all_vehicles()
        keyboard = [[InlineKeyboardButton(v["plate"], callback_data=f"veh_{v['id']}")] for v in vehicles]
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])

        text = "Select Vehicle:"
        is_admin = self.is_admin(update.effective_user.id)
        reply_markup = get_main_menu(is_admin)

        if hasattr(update, "message") and update.message:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            # Refresh the reply keyboard too
            await update.message.reply_text("Trip controls active:", reply_markup=reply_markup)
        else:
            await update.callback_query.message.reply_text(  # type: ignore
                text, reply_markup=InlineKeyboardMarkup(keyboard)
            )
        return START_TRIP_VEHICLE

    async def handle_start_vehicle(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()  # type: ignore
        if query.data == "cancel":  # type: ignore
            await query.edit_message_text("Trip cancelled.")  # type: ignore
            return ConversationHandler.END

        vehicle_id = query.data.replace("veh_", "")  # type: ignore
        context.user_data["vehicle_id"] = vehicle_id  # type: ignore
        last_odo = self.sheets.get_vehicle_last_odo(vehicle_id)
        context.user_data["last_odo"] = last_odo  # type: ignore

        await query.edit_message_text(  # type: ignore
            f"Vehicle: {vehicle_id}\nLast Reading: {last_odo} km\n\nEnter CURRENT Odometer reading:"
        )
        return START_TRIP_ODO

    async def handle_start_odo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            odo = float(update.message.text)  # type: ignore
            context.user_data["start_odo"] = odo  # type: ignore

            last_odo = context.user_data.get("last_odo", 0)  # type: ignore
            if odo < last_odo:
                await update.message.reply_text(  # type: ignore
                    f"❌ Entered KM ({odo}) is less than last trip ({last_odo}). Please recheck:"  # noqa: E501
                )
                return START_TRIP_ODO
            elif odo - last_odo > 300:
                await update.message.reply_text(  # type: ignore
                    "⚠️ Large jump detected (>300km). We have flagged this for review.\n\nPlease upload a PHOTO of the start odometer:"  # noqa: E501
                )
            else:
                await update.message.reply_text(  # type: ignore
                    "Please upload a PHOTO of the start odometer:"
                )
            return START_TRIP_IMAGE
        except ValueError:
            await update.message.reply_text("Invalid number. Please enter digits only.")  # type: ignore
            return START_TRIP_ODO

    async def handle_start_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        from telegram import KeyboardButton, ReplyKeyboardMarkup

        photo_file = await update.message.photo[-1].get_file()  # type: ignore
        photo_bytes = await photo_file.download_as_bytearray()

        driver_name = update.effective_user.first_name  # type: ignore
        trip_id = context.user_data.setdefault("trip_id", str(uuid.uuid4())[:8])  # type: ignore
        url = self.drive.save_trip_image(
            photo_bytes,
            driver_name,
            trip_id,
            "start",
            context.user_data.get("vehicle_id", "Unknown"),  # type: ignore
        )
        context.user_data["start_image_url"] = url  # type: ignore

        # Use Native Location Request
        keyboard = [[KeyboardButton("📍 Share Current Location", request_location=True)]]
        await update.message.reply_text(  # type: ignore
            "Perfect! Now tap the button below to share your **Live Pickup Location**:",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
        )
        return START_TRIP_LOC

    async def handle_start_loc(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        location = update.message.location
        if not location:
            await update.message.reply_text("Please use the button to share your location.")
            return START_TRIP_LOC

        loc_str = f"{location.latitude}, {location.longitude}"
        context.user_data["start_location"] = loc_str

        context.user_data["start_time"] = datetime.now()  # type: ignore
        context.user_data["active_trip"] = True  # type: ignore

        self.attendance.log_activity(update.effective_user.id, "V-MASTER")  # type: ignore
        self.sheets.update_vehicle_status(
            context.user_data["vehicle_id"],
            context.user_data["start_odo"],
            "On Trip",  # type: ignore
        )

        is_admin = self.is_admin(update.effective_user.id)
        await update.message.reply_text(
            "✅ Location Verified! Drive safe. Trip has started.", reply_markup=get_main_menu(is_admin)
        )
        return ConversationHandler.END

    # --- END TRIP FLOW ---
    async def end_trip_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.user_data.get("active_trip"):  # type: ignore
            await update.message.reply_text("⚠️ You don't have an active trip to end.")  # type: ignore
            return ConversationHandler.END

        # Auto-detect vehicle_id from active trip
        v_id = context.user_data.get("vehicle_id")
        if v_id:
            context.user_data["vehicle_id"] = v_id
            await update.message.reply_text(f"🏁 Ending trip for vehicle: **{v_id}**", parse_mode="Markdown")
            await update.message.reply_text("Enter current ODOMETER reading:")
            return END_TRIP_ODO

        # Fallback if vehicle_id was lost (unlikely with persistence)
        vehicles = self.sheets.get_all_vehicles()
        keyboard = [[InlineKeyboardButton(v["plate"], callback_data=f"endveh_{v['id']}")] for v in vehicles]
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
        await update.message.reply_text(
            "Which vehicle are you ending the trip for?",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return END_TRIP_VEHICLE

    async def handle_end_vehicle(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()  # type: ignore
        if query.data == "cancel":  # type: ignore
            await query.edit_message_text("Cancelled.")  # type: ignore
            return ConversationHandler.END

        context.user_data["vehicle_id"] = query.data.replace("endveh_", "")  # type: ignore
        await query.edit_message_text(  # type: ignore
            f"Ending trip for {context.user_data['vehicle_id']}. Enter END Odometer:"  # type: ignore
        )
        return END_TRIP_ODO

    async def handle_end_odo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            odo = float(update.message.text)  # type: ignore
            start_odo = float(context.user_data.get("start_odo", 0))

            # Odometer Validation
            if odo < start_odo:
                await update.message.reply_text(
                    f"⚠️ **Error**: End Odometer (`{odo}`) cannot be less than Start Odometer (`{start_odo}`).\n"
                    "Please check the reading and enter it again:",
                    parse_mode="Markdown",
                )
                return END_TRIP_ODO

            context.user_data["end_odo"] = odo  # type: ignore
            await update.message.reply_text("Upload a PHOTO of the end odometer:")  # type: ignore
            return END_TRIP_IMAGE
        except ValueError:
            await update.message.reply_text("Invalid number. Please enter digits only.")  # type: ignore
            return END_TRIP_ODO

    async def handle_end_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        from telegram import KeyboardButton, ReplyKeyboardMarkup

        photo_file = await update.message.photo[-1].get_file()  # type: ignore
        photo_bytes = await photo_file.download_as_bytearray()

        driver_name = update.effective_user.first_name  # type: ignore
        trip_id = context.user_data.get("trip_id", "Unknown")  # type: ignore
        url = self.drive.save_trip_image(
            photo_bytes,
            driver_name,
            trip_id,
            "end",
            context.user_data.get("vehicle_id", "Unknown"),  # type: ignore
        )
        context.user_data["end_image_url"] = url  # type: ignore

        # Use Native Location Request
        keyboard = [[KeyboardButton("📍 Share Drop-off Location", request_location=True)]]
        await update.message.reply_text(  # type: ignore
            "Now tap the button below to share your **Live Drop-off Location**:",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
        )
        return END_TRIP_LOC

    async def handle_end_loc(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        location = update.message.location
        if not location:
            await update.message.reply_text("Please use the button to share your location.")
            return END_TRIP_LOC

        loc_str = f"{location.latitude}, {location.longitude}"
        context.user_data["end_location"] = loc_str
        await update.message.reply_text("Location captured! 📍")

        context.user_data["end_time"] = datetime.now()  # type: ignore

        keyboard = [
            [
                InlineKeyboardButton("✅ Yes", callback_data="fuel_yes"),
                InlineKeyboardButton("❌ No", callback_data="fuel_no"),
            ]
        ]
        await update.message.reply_text(  # type: ignore
            "Did you refuel during this trip?",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return FUEL_PROMPT

    async def handle_fuel_prompt(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()  # type: ignore
        if query.data == "fuel_yes":  # type: ignore
            await query.edit_message_text("Enter Liters and Cost (e.g., '20, 2000'):")  # type: ignore
            return FUEL_DATA
        else:
            context.user_data["fuel_liters"] = "0"  # type: ignore
            context.user_data["fuel_cost"] = "0"  # type: ignore
            await query.edit_message_text("Enter Total Revenue for this trip (in ₹):")  # type: ignore
            return END_TRIP_REVENUE

    async def handle_fuel_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        data = update.message.text.split(",")  # type: ignore
        liters = data[0].strip()
        cost = data[1].strip() if len(data) > 1 else "0"

        context.user_data["fuel_liters"] = liters  # type: ignore
        context.user_data["fuel_cost"] = cost  # type: ignore

        try:
            start = float(context.user_data.get("start_odo", 0))  # type: ignore
            if start == 0:
                start = float(
                    self.sheets.get_vehicle_last_odo(
                        context.user_data.get("vehicle_id")  # type: ignore
                    )
                )
            end = float(context.user_data.get("end_odo", 0))  # type: ignore
            distance = end - start
            liters_val = float(liters)
            if liters_val > 0:
                mileage = distance / liters_val
                context.user_data["mileage"] = mileage  # type: ignore
                await update.message.reply_text(  # type: ignore
                    f"⚠️ Your mileage: {mileage:.1f} km/l (Expected: 12-15)"
                )
        except Exception:
            pass

        await update.message.reply_text("Upload a photo of the FUEL RECEIPT:")  # type: ignore
        return FUEL_IMAGE

    async def handle_fuel_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        photo_file = await update.message.photo[-1].get_file()  # type: ignore
        photo_bytes = await photo_file.download_as_bytearray()

        driver_name = update.effective_user.first_name  # type: ignore
        trip_id = context.user_data.setdefault("trip_id", str(uuid.uuid4())[:8])  # type: ignore
        url = self.drive.save_fuel_receipt(
            photo_bytes,
            driver_name,
            trip_id,
            context.user_data.get("vehicle_id", "Unknown"),  # type: ignore
            context.user_data.get("fuel_cost", 0),  # type: ignore
        )
        context.user_data["fuel_image_url"] = url  # type: ignore

        await update.message.reply_text(  # type: ignore
            "Any other expenses? (Toll/Parking/Maintenance)\nEnter total amount (or 0):"
        )
        return END_TRIP_OTHER_EXP

    async def handle_end_revenue(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            context.user_data["revenue"] = float(update.message.text)  # type: ignore
            await update.message.reply_text(  # type: ignore
                "Any other expenses? (Toll/Parking/Maintenance)\nEnter total amount (or 0):"  # noqa: E501
            )
            return END_TRIP_OTHER_EXP
        except ValueError:
            await update.message.reply_text("Invalid number. Try again:")  # type: ignore
            return END_TRIP_REVENUE

    async def handle_end_other_exp(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            other = float(update.message.text)  # type: ignore
            context.user_data["other_expenses"] = other  # type: ignore
            if other > 0:
                await update.message.reply_text(  # type: ignore
                    "Please upload a photo of the receipt for this expense (Toll/Maintenance):"  # noqa: E501
                )
                return END_TRIP_EXPENSE_PHOTO
            else:
                return await self.show_end_summary(update, context)
        except ValueError:
            await update.message.reply_text("Invalid number. Try again:")  # type: ignore
            return END_TRIP_OTHER_EXP

    async def handle_end_expense_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        photo_file = await update.message.photo[-1].get_file()  # type: ignore
        photo_bytes = await photo_file.download_as_bytearray()

        driver_name = update.effective_user.first_name  # type: ignore
        v_id = context.user_data.get("vehicle_id", "Unknown")  # type: ignore
        cost = context.user_data.get("other_expenses", 0)  # type: ignore

        url = self.drive.save_expense_receipt(photo_bytes, driver_name, v_id, cost)
        context.user_data["expense_image_url"] = url  # type: ignore

        return await self.show_end_summary(update, context)

    async def show_end_summary(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        start = context.user_data.get("start_odo")  # type: ignore
        if start is None:
            start = self.sheets.get_vehicle_last_odo(
                context.user_data.get("vehicle_id", "Unknown")  # type: ignore
            )
            context.user_data["start_odo"] = start  # type: ignore

        end = context.user_data.get("end_odo", 0)  # type: ignore
        distance = end - float(start)
        fuel = float(context.user_data.get("fuel_cost", 0))  # type: ignore
        other = context.user_data.get("other_expenses", 0)  # type: ignore
        total_expenses = fuel + other

        context.user_data["distance"] = distance  # type: ignore
        context.user_data["total_expenses"] = total_expenses  # type: ignore

        summary = (
            f"📊 *Trip Summary*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🛣 Distance: `{distance} km`\n"
            f"⛽ Fuel: `₹{fuel}`\n"
            f"🛠 Other: `₹{other}`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 *Total Spent*: `₹{total_expenses}`\n"
        )

        keyboard = [
            [
                InlineKeyboardButton("✅ Confirm", callback_data="confirm"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
            ]
        ]

        if hasattr(update, "message") and update.message:
            await update.message.reply_text(
                summary,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        else:
            await update.callback_query.message.reply_text(  # type: ignore
                summary,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )

        return END_TRIP_SUMMARY

    async def handle_end_summary(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()  # type: ignore
        if query.data == "confirm":  # type: ignore
            await query.edit_message_text("Saving trip...")  # type: ignore
            await self.complete_trip(update, context)
        else:
            await query.edit_message_text("Trip submission cancelled. Data discarded.")  # type: ignore
            context.user_data["active_trip"] = False  # type: ignore
        return ConversationHandler.END

    async def complete_trip(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            distance = context.user_data.get("distance", 0)  # type: ignore
            start_time = context.user_data.get("start_time", datetime.now())  # type: ignore
            end_time = context.user_data.get("end_time", datetime.now())  # type: ignore
            duration = int((end_time - start_time).total_seconds() / 60)

            trip_data = {
                "distance": distance,
                "duration_mins": duration,
                "mileage": context.user_data.get("mileage", 0),  # type: ignore
                "fuel_cost": float(context.user_data.get("fuel_cost", 0)),  # type: ignore
                "revenue": context.user_data.get("revenue", 0),  # type: ignore
            }

            validator = TripValidator()
            flags, score = validator.evaluate_trip(trip_data)

            trip_id = context.user_data.get("trip_id", str(uuid.uuid4())[:8])  # type: ignore
            date = datetime.now().strftime("%Y-%m-%d")

            flag_str = ", ".join(flags) if flags else "OK"
            if flag_str != "OK":
                flag_str = "🚩 " + flag_str
                self.drive.flag_trip_images(
                    date,
                    update.effective_user.first_name,
                    trip_id,  # type: ignore
                )

            trip_record = {
                "trip_id": trip_id,
                "date": date,
                "vendor_id": "V-MASTER",
                "driver_id": update.effective_user.id,  # type: ignore
                "vehicle_id": context.user_data.get("vehicle_id", "Unknown"),  # type: ignore
                "start_time": start_time.strftime("%H:%M:%S"),
                "end_time": end_time.strftime("%H:%M:%S"),
                "duration": duration,
                "start_location": context.user_data.get("start_location"),  # type: ignore
                "end_location": context.user_data.get("end_location"),  # type: ignore
                "start_odo": context.user_data.get("start_odo", 0),  # type: ignore
                "end_odo": context.user_data.get("end_odo", 0),  # type: ignore
                "distance": "=L{row}-K{row}",
                "fuel_liters": context.user_data.get("fuel_liters", 0),  # type: ignore
                "fuel_cost": context.user_data.get("fuel_cost", 0),  # type: ignore
                "other_expenses": context.user_data.get("other_expenses", 0),  # type: ignore
                "revenue": context.user_data.get("revenue", 0),  # type: ignore
                "net_profit": "=Q{row}-O{row}-P{row}",
                "driver_score": score,
                "start_image": context.user_data.get("start_image_url"),  # type: ignore
                "end_image": context.user_data.get("end_image_url"),  # type: ignore
                "fuel_image": context.user_data.get("fuel_image_url"),  # type: ignore
                "flag": flag_str,
                "remarks": "B2B Trip recorded",  # type: ignore
            }

            self.sheets.record_trip(trip_record)
            self.sheets.update_vehicle_status(
                context.user_data.get("vehicle_id", "Unknown"),  # type: ignore
                context.user_data.get("end_odo", 0),  # type: ignore
                "Idle",
            )

            is_admin = self.is_admin(update.effective_user.id)
            await update.effective_message.reply_text(  # type: ignore
                f"✅ Trip successfully recorded in the ledger!\nTrip ID: {trip_id}",
                reply_markup=get_main_menu(is_admin),
            )
        except Exception as e:
            logger.error(f"Error completing trip: {e}")
            await update.effective_message.reply_text(  # type: ignore
                "⚠️ An error occurred while saving the trip. Please contact admin."
            )
        finally:
            context.user_data["active_trip"] = False  # type: ignore
