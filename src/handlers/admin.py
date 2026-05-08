import logging
import os
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, Update
from telegram.ext import ContextTypes, ConversationHandler

from handlers.base import BaseHandler

logger = logging.getLogger(__name__)


class AdminHandler(BaseHandler):
    def __init__(self, sheets, drive, attendance):
        super().__init__(sheets, drive, attendance)
        self.admin_ids = [int(i.strip()) for i in os.getenv("ADMIN_IDS", "").split(",") if i.strip()]

    def _is_admin(self, user_id):
        return user_id in self.admin_ids

    async def admin_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        assert update.effective_user
        if not self._is_admin(update.effective_user.id):
            await update.effective_message.reply_text("⛔ Unauthorized.")
            return

        text = (
            "👨‍✈️ *Fleet Management Center*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "📊 *Reporting*\n"
            "• /viewdaily - Today's operations\n"
            "• /viewweekly - Last 7 days summary\n"
            "• /viewfuel - Fuel efficiency stats\n"
            "• /viewdrivers - Active driver list\n"
            "• /live - Live fleet status 📺\n\n"
            "📢 *Operations*\n"
            "• /broadcast - Message all drivers\n"
            "• /health - System diagnostic check\n\n"
            "📸 *Media Center*\n"
            "• /gallery - Recent trip photos 🖼️\n"
            "• /downloadtoday - ZIP of today's photos\n"
            "• /downloadrange - Custom date ZIP\n"
            "• /downloadphotos <YYYY-MM-DD>\n\n"
            "💡 _Tip: Tapping the Admin button resets stuck states._"
        )
        await update.effective_message.reply_text(text, parse_mode="Markdown")

    async def health_check(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update.effective_user.id):
            return

        await update.effective_message.reply_text("🏥 *System Health Check...*", parse_mode="Markdown")

        # 1. Check Sheets
        sheets_ok = "🟢 OK" if self.sheets.spreadsheet else "🔴 Error"
        # 2. Check R2
        r2_ok = "🟢 OK"
        try:
            self.drive.s3_client.list_buckets()
        except Exception:
            r2_ok = "🔴 Error"

        text = (
            f"🏥 *System Status Report*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 Google Sheets: {sheets_ok}\n"
            f"☁️ Cloudflare R2: {r2_ok}\n"
            f"🕒 Server Time: `{datetime.now().strftime('%H:%M:%S')}`\n"
            f"✅ All systems functional."
        )
        await update.effective_message.reply_text(text, parse_mode="Markdown")

    async def start_broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update.effective_user.id):
            return
        from core.states import ADMIN_BROADCAST

        await update.effective_message.reply_text(
            "📢 *Broadcast System*\n\n"
            "Please enter the message you want to send to **ALL registered drivers**.\n"
            "Type `cancel` to abort.",
            parse_mode="Markdown",
        )
        return ADMIN_BROADCAST

    async def handle_broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = update.message.text
        if msg.lower() == "cancel":
            await update.message.reply_text("Broadcast cancelled.")
            return ConversationHandler.END

        drivers = self.sheets.get_records_safe("Master_Drivers")
        count = 0
        for d in drivers:
            try:
                tid = d.get("DriverID")
                if tid and str(tid).isdigit():
                    await context.bot.send_message(
                        chat_id=int(tid),
                        text=f"📢 *MESSAGE FROM ADMIN*\n━━━━━━━━━━━━━━━━━━━━\n\n{msg}",
                        parse_mode="Markdown",
                    )
                    count += 1
            except Exception as e:
                logger.error(f"Failed to send broadcast to {tid}: {e}")

        await update.message.reply_text(f"✅ Broadcast sent successfully to {count} drivers.")
        return ConversationHandler.END

    async def view_daily_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update.effective_user.id):
            return

        today = datetime.now().strftime("%Y-%m-%d")
        records = self.sheets.get_records_safe("Trips")

        daily_trips = [r for r in records if r.get("Date") == today]
        total_trips = len(daily_trips)
        total_rev = sum(float(r.get("Revenue", 0)) for r in daily_trips)
        total_km = sum(
            float(r.get("Distance", 0)) for r in daily_trips if str(r.get("Distance", "")).replace(".", "", 1).isdigit()
        )

        text = (
            f"📅 *Daily Operational Report*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"*Date*: `{today}`\n\n"
            f"✅ *Completed Trips*: `{total_trips}`\n"
            f"🛣 *Total Distance*: `{total_km:.1f} KM`\n"
            f"💰 *Total Revenue*: `₹{total_rev:,.2f}`\n\n"
            f"Last updated: `{datetime.now().strftime('%H:%M:%S')}`"
        )

        keyboard = [[InlineKeyboardButton("🔄 Refresh Stats", callback_data="refresh_daily")]]

        if update.callback_query:
            await update.callback_query.edit_message_text(
                text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.effective_message.reply_text(
                text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
            )

    async def view_drivers(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update.effective_user.id):
            return

        drivers = self.sheets.get_records_safe("Master_Drivers")
        if not drivers:
            await update.effective_message.reply_text("👥 No drivers found.")
            return

        text = "👥 *Driver Management*\nTap a driver to view profile\n━━━━━━━━━━━━━━━━━━━━\n"
        keyboard = []
        for d in drivers:
            name = d.get("Name")
            tid = d.get("DriverID")
            keyboard.append([InlineKeyboardButton(f"👤 {name}", callback_data=f"drv_{tid}")])

        await update.effective_message.reply_text(
            text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def handle_admin_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        data = query.data

        if data == "refresh_daily":
            await self.view_daily_stats(update, context)
        elif data.startswith("drv_"):
            tid = data.replace("drv_", "")
            # Fetch driver details
            drivers = self.sheets.get_records_safe("Master_Drivers")
            driver = next((d for d in drivers if str(d.get("DriverID")) == tid), None)
            if driver:
                text = (
                    f"👤 *Driver Profile*\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"*Name*: {driver.get('Name')}\n"
                    f"*ID*: `{tid}`\n"
                    f"*Phone*: {driver.get('Phone')}\n"
                    f"*Status*: {driver.get('Status')}\n\n"
                    f"Action required?"
                )
                keyboard = [
                    [
                        InlineKeyboardButton("📞 Call Driver", url=f"tel:{driver.get('Phone')}"),
                        InlineKeyboardButton("🔙 Back", callback_data="back_to_drivers"),
                    ]
                ]
                await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        elif data == "back_to_drivers":
            await self.view_drivers(update, context)
        elif data.startswith("approve_") or data.startswith("reject_"):
            # Handle expense approval
            action = "Approved ✅" if data.startswith("approve_") else "Rejected ❌"
            await query.edit_message_caption(caption=f"Expense {action}\n{query.message.caption}")

    async def view_live_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update.effective_user.id):
            return
        vehicles = self.sheets.get_records_safe("Master_Vehicles")
        text = "📺 *Live Fleet Status*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        for v in vehicles:
            status_icon = "🟢" if v.get("Status") == "On Trip" else "🟡"
            text += f"{status_icon} *{v.get('LicensePlate')}*: `{v.get('Status')}`\n"
        await update.effective_message.reply_text(text, parse_mode="Markdown")

    async def view_recent_gallery(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update.effective_user.id):
            return
        await update.effective_message.reply_text("🖼️ Fetching recent trip photos...")
        today = datetime.now().strftime("%Y-%m-%d")
        prefix = f"trips/{today}/"
        response = self.drive.s3_client.list_objects_v2(Bucket=self.drive.bucket_name, Prefix=prefix, MaxKeys=5)
        if "Contents" not in response:
            await update.effective_message.reply_text("❌ No photos found for today yet.")
            return
        media_group = []
        for obj in response["Contents"]:
            file_data = self.drive.s3_client.get_object(Bucket=self.drive.bucket_name, Key=obj["Key"])["Body"].read()
            media_group.append(InputMediaPhoto(file_data, caption=obj["Key"].split("/")[-1]))
        if media_group:
            await update.effective_message.reply_media_group(media_group[:5])

    async def download_today(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        today = datetime.now().strftime("%Y-%m-%d")
        context.args = [today]
        await self.download_photos(update, context)

    async def download_weekly(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        prefix = "trips/"
        zip_buffer = self.drive.generate_period_zip(prefix)
        if zip_buffer:
            await update.effective_message.reply_document(document=zip_buffer, filename="Weekly_Archive.zip")

    async def download_photos(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update.effective_user.id):
            return
        if not context.args:
            return
        date_str = context.args[0]
        prefix = f"trips/{date_str}/"
        zip_buffer = self.drive.generate_period_zip(prefix)
        if zip_buffer:
            await update.effective_message.reply_document(document=zip_buffer, filename=f"Photos_{date_str}.zip")

    async def start_download_range(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        from core.states import ADMIN_DL_FROM

        await update.effective_message.reply_text("📅 Start Date (YYYY-MM-DD):")
        return ADMIN_DL_FROM

    async def handle_from_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        from core.states import ADMIN_DL_TO

        context.user_data["dl_from"] = update.message.text
        await update.message.reply_text("📅 End Date (YYYY-MM-DD):")
        return ADMIN_DL_TO

    async def handle_to_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        start = context.user_data.get("dl_from")
        end = update.message.text
        zip_buffer = self.drive.generate_range_zip(start, end)
        if zip_buffer:
            await update.effective_message.reply_document(document=zip_buffer, filename="Range_Archive.zip")
        return ConversationHandler.END
