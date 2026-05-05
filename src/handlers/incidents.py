from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from handlers.base import BaseHandler
from core.states import REPORT_VEHICLE, REPORT_DESC, REPORT_PHOTO
from utils.ui import get_main_menu

class IncidentHandler(BaseHandler):
    async def report_damage_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        vehicles = self.sheets.get_all_vehicles()
        keyboard = [[InlineKeyboardButton(v, callback_data=f"rep_{v}")] for v in vehicles]
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
        await update.message.reply_text("Which vehicle has damage or an incident?", reply_markup=InlineKeyboardMarkup(keyboard))
        return REPORT_VEHICLE

    async def handle_report_vehicle(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        if query.data == "cancel":
            await query.edit_message_text("Cancelled.")
            return ConversationHandler.END
            
        context.user_data["report_vehicle"] = query.data.replace("rep_", "")
        await query.edit_message_text("Please describe the damage or incident briefly:")
        return REPORT_DESC

    async def handle_report_desc(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data["report_desc"] = update.message.text
        await update.message.reply_text("Please upload a PHOTO of the damage:")
        return REPORT_PHOTO

    async def handle_report_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        
        driver_name = update.effective_user.first_name
        v_id = context.user_data.get("report_vehicle", "Unknown")
        
        self.drive.save_incident_report(photo_bytes, driver_name, v_id)
        
        await update.message.reply_text("✅ Incident reported and saved for insurance/audit.", reply_markup=get_main_menu())
        return ConversationHandler.END
