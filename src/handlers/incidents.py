from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from core.states import REPORT_DESC, REPORT_PHOTO, REPORT_VEHICLE
from handlers.base import BaseHandler
from utils.ui import get_main_menu


class IncidentHandler(BaseHandler):
    async def report_damage_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        vehicles = self.sheets.get_all_vehicles()
        keyboard = [[InlineKeyboardButton(v, callback_data=f"rep_{v}")] for v in vehicles]
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
        await update.message.reply_text(  # type: ignore
            "Which vehicle has damage or an incident?",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return REPORT_VEHICLE

    async def handle_report_vehicle(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()  # type: ignore
        if query.data == "cancel":  # type: ignore
            await query.edit_message_text("Cancelled.")  # type: ignore
            return ConversationHandler.END

        context.user_data["report_vehicle"] = query.data.replace("rep_", "")  # type: ignore
        await query.edit_message_text("Please describe the damage or incident briefly:")  # type: ignore
        return REPORT_DESC

    async def handle_report_desc(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data["report_desc"] = update.message.text  # type: ignore
        await update.message.reply_text("Please upload a PHOTO of the damage:")  # type: ignore
        return REPORT_PHOTO

    async def handle_report_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        photo_file = await update.message.photo[-1].get_file()  # type: ignore
        photo_bytes = await photo_file.download_as_bytearray()

        driver_name = update.effective_user.first_name  # type: ignore
        v_id = context.user_data.get("report_vehicle", "Unknown")  # type: ignore

        self.drive.save_incident_report(photo_bytes, driver_name, v_id)

        await update.message.reply_text(  # type: ignore
            "✅ Incident reported and saved for insurance/audit.",
            reply_markup=get_main_menu(),
        )
        return ConversationHandler.END
