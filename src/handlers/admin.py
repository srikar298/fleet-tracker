import os
from datetime import datetime

from telegram import Update
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
            "👨‍✈️ *Admin Command Center*\n\n"
            "/view_daily - Today's operational stats\n"
            "/view_weekly - Last 7 days summary\n"
            "/view_fuel - Fleet fuel efficiency (KM/L)\n"
            "/download_photos <YYYY-MM-DD> - Get ZIP of all photos for a date"
        )
        await update.effective_message.reply_text(text, parse_mode="Markdown")

    async def view_daily_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        assert update.effective_user
        if not self._is_admin(update.effective_user.id):
            return

        today = datetime.now().strftime("%Y-%m-%d")
        records = self.sheets.get_records_safe("Trips")

        daily_trips = [r for r in records if r.get("Date") == today]
        total_trips = len(daily_trips)
        total_rev = sum(float(r.get("Revenue", 0)) for r in daily_trips)

        text = (
            f"📅 *Daily Report: {today}*\n\n"
            f"Trips Completed: {total_trips}\n"
            f"Total Revenue: ₹{total_rev:.2f}\n"
            f"Fleet Status: View GSheets for live dashboard."
        )
        await update.effective_message.reply_text(text, parse_mode="Markdown")

    async def download_photos(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        assert update.effective_user
        if not self._is_admin(update.effective_user.id):
            return

        if not context.args:
            await update.effective_message.reply_text("Usage: /download_photos YYYY-MM-DD")
            return

        date_str = context.args[0]
        await update.effective_message.reply_text(f"📦 Generating ZIP for {date_str}... please wait.")

        # Key prefix in R2: trips/YYYY-MM-DD/
        prefix = f"trips/{date_str}/"
        zip_buffer = self.drive.generate_period_zip(prefix)

        if zip_buffer:
            await update.effective_message.reply_document(
                document=zip_buffer, filename=f"Fleet_Photos_{date_str}.zip", caption=f"All trip photos for {date_str}"
            )
        else:
            await update.effective_message.reply_text(f"❌ No photos found for {date_str}.")

    async def view_fuel_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        assert update.effective_user
        if not self._is_admin(update.effective_user.id):
            return

        report = self.sheets.get_fuel_efficiency_report()
        if not report:
            await update.effective_message.reply_text("No fuel data available yet.")
            return

        text = "⛽ *Fleet Fuel Efficiency (KM/L)*\n\n"
        for v in report:
            status = "🟢" if v["kml"] > 15 else "🟠" if v["kml"] > 10 else "🔴"
            text += f"{status} *{v['id']}*: {v['kml']:.2f} KM/L ({v['total_km']} km total)\n"

        await update.effective_message.reply_text(text, parse_mode="Markdown")
