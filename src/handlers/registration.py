from typing import Any

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from core.states import (
    REGISTER_LICENSE,
    REGISTER_LICENSE_PHOTO,
    REGISTER_NAME,
    REGISTER_PHONE,
)
from handlers.base import BaseHandler
from utils.ui import get_main_menu


class RegistrationHandler(BaseHandler):
    async def register_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.effective_user or not update.message:
            return None
        driver = self.sheets.get_driver_by_id(update.effective_user.id)

        if driver:
            text = (
                f"👤 *Your Profile*\n\n"
                f"*Name*: {driver.get('Name')}\n"
                f"*Phone*: {driver.get('Phone')}\n"
                f"*License*: {driver.get('License')}\n"
                f"*Vendor*: {driver.get('VendorID')}\n"
                f"*Status*: {driver.get('Status')}\n\n"
                f"Your details are already registered!"
            )
            is_admin = self.is_admin(update.effective_user.id)
            await update.message.reply_text(text, parse_mode="Markdown", reply_markup=get_main_menu(is_admin))
            return ConversationHandler.END

        await update.message.reply_text("Let's register you! What is your Full Name?")
        return REGISTER_NAME

    async def handle_register_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.message or not update.message.text or context.user_data is None:
            return None
        context.user_data["driver_name"] = update.message.text
        await update.message.reply_text("Great! Now, what is your Phone Number?")
        return REGISTER_PHONE

    async def handle_register_phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.message or not update.message.text or context.user_data is None:
            return None
        context.user_data["driver_phone"] = update.message.text
        await update.message.reply_text("Almost done. What is your Driving License Number (or ID)?")
        return REGISTER_LICENSE

    async def handle_register_license(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.message or not update.message.text or context.user_data is None:
            return None
        context.user_data["license_num"] = update.message.text
        await update.message.reply_text("Please upload a PHOTO of your Driving License for KYC compliance:")
        return REGISTER_LICENSE_PHOTO

    async def handle_register_license_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        if not update.message or not update.message.photo or not update.effective_user or context.user_data is None:
            return None
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()

        name = str(context.user_data.get("driver_name", "Unknown"))
        photo_url = self.drive.save_kyc_document(photo_bytes, name) or "N/A"

        license_num = str(context.user_data.get("license_num", "Unknown"))
        phone = str(context.user_data.get("driver_phone", "Unknown"))
        self.sheets.register_driver(update.effective_user.id, name, license_num, photo_url, phone)

        is_admin = self.is_admin(update.effective_user.id)
        await update.message.reply_text(
            f"✅ KYC complete! Registered {name} successfully.",
            reply_markup=get_main_menu(is_admin),
        )
        return ConversationHandler.END
