import os
from datetime import datetime

from telegram import InputMediaPhoto, Update
from telegram.ext import ContextTypes

from handlers.base import BaseHandler


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
            "📸 *Media Center*\n"
            "• /gallery - Recent trip photos 🖼️\n"
            "• /downloadtoday - ZIP of today's photos\n"
            "• /downloadrange - Custom date ZIP\n"
            "• /downloadphotos <YYYY-MM-DD>\n\n"
            "💡 _Tip: Tapping the Admin button resets stuck states._"
        )
        await update.effective_message.reply_text(text, parse_mode="Markdown")

    async def view_daily_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update.effective_user.id):
            return

        today = datetime.now().strftime("%Y-%m-%d")
        records = self.sheets.get_records_safe("Trips")

        daily_trips = [r for r in records if r.get("Date") == today]
        total_trips = len(daily_trips)
        total_rev = sum(float(r.get("Revenue", 0)) for r in daily_trips)
        total_km = sum(float(r.get("Distance", 0)) for r in daily_trips if str(r.get("Distance", "")).isdigit())

        text = (
            f"📅 *Daily Operational Report*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"*Date*: `{today}`\n\n"
            f"✅ *Completed Trips*: `{total_trips}`\n"
            f"🛣 *Total Distance*: `{total_km:.1f} KM`\n"
            f"💰 *Total Revenue*: `₹{total_rev:,.2f}`\n\n"
            f"🔗 [View Live Ledger](https://docs.google.com/spreadsheets/d/{os.getenv('GOOGLE_SHEETS_ID')})"
        )
        await update.effective_message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)

    async def view_fuel_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update.effective_user.id):
            return

        report = self.sheets.get_fuel_efficiency_report()
        if not report:
            await update.effective_message.reply_text("⛽ No fuel data available yet.")
            return

        text = "⛽ *Fleet Fuel Efficiency (KM/L)*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        for v in report:
            status = "🟢" if v["kml"] > 15 else "🟠" if v["kml"] > 10 else "🔴"
            text += f"{status} *{v['id']}*: `{v['kml']:.2f} KM/L`\n   └ _Distance: {v['total_km']} km_\n\n"

        await update.effective_message.reply_text(text, parse_mode="Markdown")

    async def view_drivers(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update.effective_user.id):
            return

        drivers = self.sheets.get_records_safe("Master_Drivers")
        if not drivers:
            await update.effective_message.reply_text("👥 No drivers found.")
            return

        text = "👥 *Registered Drivers Directory*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        for d in drivers:
            status = "✅" if d.get("Status") == "Active" else "🛑"
            text += f"{status} *{d.get('Name')}*\n   └ ID: `{d.get('DriverID')}`\n   └ Phone: `{d.get('Phone')}`\n\n"

        await update.effective_message.reply_text(text, parse_mode="Markdown")

    async def view_live_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update.effective_user.id):
            return

        vehicles = self.sheets.get_records_safe("Master_Vehicles")
        if not vehicles:
            await update.effective_message.reply_text("📺 No vehicle data.")
            return

        text = "📺 *Live Fleet Status*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        for v in vehicles:
            status_icon = "🟢" if v.get("Status") == "On Trip" else "🟡"
            text += f"{status_icon} *{v.get('LicensePlate')}*\n   └ Status: `{v.get('Status')}`\n   └ Last Odo: `{v.get('Last_Odometer')}`\n\n"

        await update.effective_message.reply_text(text, parse_mode="Markdown")

    async def view_recent_gallery(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update.effective_user.id):
            return

        await update.effective_message.reply_text("🖼️ Fetching recent trip photos...")

        today = datetime.now().strftime("%Y-%m-%d")
        prefix = f"trips/{today}/"

        # List files in R2
        response = self.drive.s3_client.list_objects_v2(Bucket=self.drive.bucket_name, Prefix=prefix, MaxKeys=5)

        if "Contents" not in response:
            await update.effective_message.reply_text("❌ No photos found for today yet.")
            return

        media_group = []
        for obj in response["Contents"]:
            key = obj["Key"]
            # We use the public URL if available, otherwise we'd need to download and send
            # For this implementation, let's assume we can generate a temporary URL or similar
            # Since we have the binary data, let's just send the last 3-5 images
            file_data = self.drive.s3_client.get_object(Bucket=self.drive.bucket_name, Key=key)["Body"].read()
            media_group.append(InputMediaPhoto(file_data, caption=key.split("/")[-1]))

        if media_group:
            await update.effective_message.reply_media_group(media_group[:5])
        else:
            await update.effective_message.reply_text("❌ No viewable photos found.")

    async def download_today(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        today = datetime.now().strftime("%Y-%m-%d")
        context.args = [today]
        await self.download_photos(update, context)

    async def download_weekly(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.effective_message.reply_text("📦 Fetching weekly photo archive...")
        prefix = "trips/"
        zip_buffer = self.drive.generate_period_zip(prefix)
        if zip_buffer:
            await update.effective_message.reply_document(
                document=zip_buffer, filename=f"Fleet_Weekly_{datetime.now().strftime('%V')}.zip"
            )
        else:
            await update.effective_message.reply_text("❌ No photos found in the archive.")

    async def download_photos(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update.effective_user.id):
            return

        if not context.args:
            await update.effective_message.reply_text("Usage: `/downloadphotos YYYY-MM-DD`", parse_mode="Markdown")
            return

        date_str = context.args[0]
        await update.effective_message.reply_text(f"📦 Generating ZIP for `{date_str}`...", parse_mode="Markdown")

        prefix = f"trips/{date_str}/"
        zip_buffer = self.drive.generate_period_zip(prefix)

        if zip_buffer:
            await update.effective_message.reply_document(
                document=zip_buffer,
                filename=f"Fleet_Photos_{date_str}.zip",
                caption=f"📂 Photos for {date_str}\nStructure: Driver > TripID > Photo",
            )
        else:
            await update.effective_message.reply_text(f"❌ No photos found for `{date_str}`.", parse_mode="Markdown")
