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
    async def register_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            await update.message.reply_text(text, parse_mode="Markdown", reply_markup=get_main_menu())
            return ConversationHandler.END

        await update.message.reply_text("Let's register you! What is your Full Name?")
        return REGISTER_NAME

    async def handle_register_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data["driver_name"] = update.message.text  # type: ignore
        await update.message.reply_text("Great! Now, what is your Phone Number?")  # type: ignore
        return REGISTER_PHONE

    async def handle_register_phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data["driver_phone"] = update.message.text  # type: ignore
        await update.message.reply_text(  # type: ignore
            "Almost done. What is your Driving License Number (or ID)?"
        )
        return REGISTER_LICENSE

    async def handle_register_license(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data["license_num"] = update.message.text  # type: ignore
        await update.message.reply_text(  # type: ignore
            "Please upload a PHOTO of your Driving License for KYC compliance:"
        )
        return REGISTER_LICENSE_PHOTO

    async def handle_register_license_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        photo_file = await update.message.photo[-1].get_file()  # type: ignore
        photo_bytes = await photo_file.download_as_bytearray()

        name = context.user_data.get("driver_name", "Unknown")  # type: ignore
        self.drive.save_kyc_document(photo_bytes, name)

        license_num = context.user_data.get("license_num", "Unknown")  # type: ignore
        phone = context.user_data.get("driver_phone", "Unknown")  # type: ignore
        self.sheets.register_driver(update.effective_user.id, name, license_num, phone)  # type: ignore

        await update.message.reply_text(  # type: ignore
            f"✅ KYC complete! Registered {name} successfully.",
            reply_markup=get_main_menu(),
        )
        return ConversationHandler.END
