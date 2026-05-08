import logging
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    PicklePersistence,
    filters,
)

from core.states import (
    DAILY_TARGET_TYPE,
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
    REGISTER_LICENSE,
    REGISTER_LICENSE_PHOTO,
    REGISTER_NAME,
    REGISTER_PHONE,
    REPORT_DESC,
    REPORT_PHOTO,
    REPORT_VEHICLE,
    START_TRIP_IMAGE,
    START_TRIP_LOC,
    START_TRIP_ODO,
    START_TRIP_VEHICLE,
)
from handlers.admin import AdminHandler
from handlers.incidents import IncidentHandler
from handlers.registration import RegistrationHandler
from handlers.trips import TripHandler
from services.attendance_service import AttendanceService
from services.backup_service import BackupService
from services.cloudflare_service import CloudflareR2Service
from services.sheets_service import SheetsService
from utils.ui import get_main_menu

# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


class FleetBot:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.admin_ids = [int(i.strip()) for i in os.getenv("ADMIN_IDS", "").split(",") if i.strip()]

        # Initialize Core Services (Dependency Injection)
        self.sheets = SheetsService()
        self.drive = CloudflareR2Service()
        self.attendance = AttendanceService(self.sheets)

        # Initialize Domain Handlers
        self.reg_handler = RegistrationHandler(self.sheets, self.drive, self.attendance)
        self.inc_handler = IncidentHandler(self.sheets, self.drive, self.attendance)
        self.trip_handler = TripHandler(self.sheets, self.drive, self.attendance)
        self.admin_handler = AdminHandler(self.sheets, self.drive, self.attendance)
        self.backup = BackupService(self.sheets, self.drive)

        # Initialize Scheduler for Backups
        self.scheduler = AsyncIOScheduler()
        self.scheduler.add_job(self.backup.run_daily_backup, "cron", hour=0, minute=0)

    def is_admin(self, user_id):
        return user_id in self.admin_ids

    async def post_init(self, application: Application) -> None:
        """Starts the scheduler after the event loop is running."""
        self.scheduler.start()
        logger.info("Scheduler started successfully in post_init.")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        is_admin = self.is_admin(update.effective_user.id)
        await update.message.reply_text(  # type: ignore
            "Welcome to FleetTracker! 🚛\nUse the menu below to navigate.",
            reply_markup=get_main_menu(is_admin),
        )

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        is_admin = self.is_admin(update.effective_user.id)
        await update.message.reply_text(  # type: ignore
            "Operation cancelled.", reply_markup=get_main_menu(is_admin)
        )
        return ConversationHandler.END

    async def today_summary_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        summary = self.sheets.get_driver_today_summary(update.effective_user.id)  # type: ignore
        is_admin = self.is_admin(update.effective_user.id)
        text = (
            f"📊 *Today's Summary*\n"
            f"Trips: {summary['trips']}\n"
            f"KM: {summary['km']} km\n"
            f"Fuel: ₹{summary['fuel']}\n"
            f"Revenue: ₹{summary['revenue']}\n"
            f"------------\n"
            f"Net: ₹{summary['net']}"
        )
        await update.message.reply_text(  # type: ignore
            text, parse_mode="Markdown", reply_markup=get_main_menu(is_admin)
        )
        return ConversationHandler.END

    async def leaderboard_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        is_admin = self.is_admin(update.effective_user.id)
        await update.message.reply_text("Fetching live leaderboard... 🔄")  # type: ignore
        lb_text = self.sheets.get_live_leaderboard()
        await update.message.reply_text(  # type: ignore
            lb_text, parse_mode="Markdown", reply_markup=get_main_menu(is_admin)
        )
        return ConversationHandler.END

    def run(self):
        # Persistence for stateful conversations across restarts
        persistence = PicklePersistence(filepath="bot_state.pkl")

        application = Application.builder().token(self.token).persistence(persistence).post_init(self.post_init).build()

        conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler("start", self.start),
                MessageHandler(filters.Regex("^👤 Profile$"), self.reg_handler.register_cmd),
                MessageHandler(filters.Regex("^🚗 Start Trip$"), self.trip_handler.start_trip_cmd),
                MessageHandler(filters.Regex("^🛑 End Trip$"), self.trip_handler.end_trip_cmd),
                MessageHandler(filters.Regex("^📊 Today Summary$"), self.today_summary_cmd),
                MessageHandler(filters.Regex("^🏆 Leaderboard$"), self.leaderboard_cmd),
                MessageHandler(filters.Regex("^👨‍✈️ Admin Panel$"), self.admin_handler.admin_menu),
                MessageHandler(
                    filters.Regex("^⚠️ Report Damage$"),
                    self.inc_handler.report_damage_cmd,
                ),
                MessageHandler(filters.Regex("^❌ Cancel$"), self.cancel),
            ],
            states={
                # Registration Routing
                REGISTER_NAME: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.reg_handler.handle_register_name,
                    )
                ],
                REGISTER_PHONE: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.reg_handler.handle_register_phone,
                    )
                ],
                REGISTER_LICENSE: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.reg_handler.handle_register_license,
                    )
                ],
                REGISTER_LICENSE_PHOTO: [MessageHandler(filters.PHOTO, self.reg_handler.handle_register_license_photo)],
                # Incident Routing
                REPORT_VEHICLE: [CallbackQueryHandler(self.inc_handler.handle_report_vehicle)],
                REPORT_DESC: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.inc_handler.handle_report_desc,
                    )
                ],
                REPORT_PHOTO: [MessageHandler(filters.PHOTO, self.inc_handler.handle_report_photo)],
                # Gamification Routing (handled by trips)
                DAILY_TARGET_TYPE: [CallbackQueryHandler(self.trip_handler.handle_target_type)],
                DAILY_TARGET_VALUE: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.trip_handler.handle_target_value,
                    )
                ],
                # Start Trip Routing
                START_TRIP_VEHICLE: [CallbackQueryHandler(self.trip_handler.handle_start_vehicle)],
                START_TRIP_ODO: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.trip_handler.handle_start_odo,
                    )
                ],
                START_TRIP_IMAGE: [MessageHandler(filters.PHOTO, self.trip_handler.handle_start_image)],
                START_TRIP_LOC: [
                    MessageHandler(
                        filters.LOCATION | filters.TEXT & ~filters.COMMAND,
                        self.trip_handler.handle_start_loc,
                    )
                ],
                # End Trip Routing
                END_TRIP_VEHICLE: [CallbackQueryHandler(self.trip_handler.handle_end_vehicle)],
                END_TRIP_ODO: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.trip_handler.handle_end_odo,
                    )
                ],
                END_TRIP_IMAGE: [MessageHandler(filters.PHOTO, self.trip_handler.handle_end_image)],
                END_TRIP_LOC: [
                    MessageHandler(
                        filters.LOCATION | filters.TEXT & ~filters.COMMAND,
                        self.trip_handler.handle_end_loc,
                    )
                ],
                FUEL_PROMPT: [CallbackQueryHandler(self.trip_handler.handle_fuel_prompt)],
                FUEL_DATA: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.trip_handler.handle_fuel_data,
                    )
                ],
                FUEL_IMAGE: [MessageHandler(filters.PHOTO, self.trip_handler.handle_fuel_image)],
                END_TRIP_REVENUE: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.trip_handler.handle_end_revenue,
                    )
                ],
                END_TRIP_OTHER_EXP: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.trip_handler.handle_end_other_exp,
                    )
                ],
                END_TRIP_EXPENSE_PHOTO: [MessageHandler(filters.PHOTO, self.trip_handler.handle_end_expense_photo)],
                END_TRIP_SUMMARY: [CallbackQueryHandler(self.trip_handler.handle_end_summary)],
            },
            fallbacks=[
                CommandHandler("start", self.start),
                MessageHandler(filters.Regex("^❌ Cancel$"), self.cancel),
            ],
        )

        application.add_handler(conv_handler)

        # Admin Commands
        application.add_handler(CommandHandler("admin", self.admin_handler.admin_menu))
        application.add_handler(CommandHandler("view_daily", self.admin_handler.view_daily_stats))
        application.add_handler(CommandHandler("view_fuel", self.admin_handler.view_fuel_stats))
        application.add_handler(CommandHandler("download_photos", self.admin_handler.download_photos))

        application.run_polling()


if __name__ == "__main__":
    FleetBot().run()
