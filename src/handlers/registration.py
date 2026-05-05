from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from handlers.base import BaseHandler
from core.states import REGISTER_NAME, REGISTER_PHONE, REGISTER_LICENSE, REGISTER_LICENSE_PHOTO
from utils.ui import get_main_menu

class RegistrationHandler(BaseHandler):
    async def register_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Let's register you! What is your Full Name?")
        return REGISTER_NAME

    async def handle_register_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data["driver_name"] = update.message.text
        await update.message.reply_text("Great! Now, what is your Phone Number?")
        return REGISTER_PHONE

    async def handle_register_phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data["driver_phone"] = update.message.text
        await update.message.reply_text("Almost done. What is your Driving License Number (or ID)?")
        return REGISTER_LICENSE

    async def handle_register_license(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data["license_num"] = update.message.text
        await update.message.reply_text("Please upload a PHOTO of your Driving License for KYC compliance:")
        return REGISTER_LICENSE_PHOTO

    async def handle_register_license_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        
        name = context.user_data.get("driver_name", "Unknown")
        self.drive.save_kyc_document(photo_bytes, name)
        
        license_num = context.user_data.get("license_num", "Unknown")
        phone = context.user_data.get("driver_phone", "Unknown")
        self.sheets.register_driver(update.effective_user.id, name, license_num, phone)
        
        await update.message.reply_text(f"✅ KYC complete! Registered {name} successfully.", reply_markup=get_main_menu())
        return ConversationHandler.END
