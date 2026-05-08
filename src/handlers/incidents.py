from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from core.states import REPORT_DESC, REPORT_PHOTO, REPORT_VEHICLE
from handlers.base import BaseHandler
from utils.ui import get_main_menu


class IncidentHandler(BaseHandler):
    async def report_damage_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.message:
            return None
        vehicles = self.sheets.get_all_vehicles()
        keyboard: list[list[InlineKeyboardButton]] = [
            [InlineKeyboardButton(v["plate"], callback_data=f"rep_{v['id']}")] for v in vehicles
        ]
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
        await update.message.reply_text(
            "Which vehicle has damage or an incident?",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return REPORT_VEHICLE

    async def handle_report_vehicle(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        query = update.callback_query
        if not query or not query.data:
            return None
        await query.answer()
        if query.data == "cancel":
            await query.edit_message_text("Cancelled.")
            return ConversationHandler.END

        if context.user_data is not None:
            context.user_data["report_vehicle"] = query.data.replace("rep_", "")
        await query.edit_message_text("Please describe the damage or incident briefly:")
        return REPORT_DESC

    async def handle_report_desc(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.message or not update.message.text:
            return None
        if context.user_data is not None:
            context.user_data["report_desc"] = update.message.text
        await update.message.reply_text("Please upload a PHOTO of the damage:")
        return REPORT_PHOTO

    async def handle_report_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.message or not update.message.photo or not update.effective_user or context.user_data is None:
            return None
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()

        driver_name = str(update.effective_user.first_name)
        v_id = str(context.user_data.get("report_vehicle", "Unknown"))

        self.drive.save_incident_report(photo_bytes, driver_name, v_id)

        is_admin = self.is_admin(update.effective_user.id)
        await update.message.reply_text(
            "✅ Incident reported and saved for insurance/audit.",
            reply_markup=get_main_menu(is_admin),
        )
        return ConversationHandler.END
