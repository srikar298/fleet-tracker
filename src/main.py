import logging
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from telegram import BotCommand, MenuButtonDefault, Update
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
    ADMIN_BROADCAST,
    ADMIN_DL_FROM,
    ADMIN_DL_TO,
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
        """Starts the scheduler and registers bot commands."""
        # 1. Start Background Scheduler
        self.scheduler.start()
        logger.info("Scheduler started successfully in post_init.")

        # 2. Register Bot Commands for the Menu Button
        commands = [
            BotCommand("start", "🚀 Main Menu"),
            BotCommand("admin", "👨‍✈️ Admin Center"),
            BotCommand("viewdaily", "📊 Today's Stats"),
            BotCommand("live", "📺 Live Fleet Watch"),
            BotCommand("gallery", "🖼️ Recent Photo Gallery"),
            BotCommand("cancel", "❌ Cancel Current Action"),
        ]
        await application.bot.set_my_commands(commands)
        logger.info("Bot commands registered successfully.")

        # 3. Set the Persistent Menu Button (The blue button in the corner)
        await application.bot.set_chat_menu_button(menu_button=MenuButtonDefault())
        logger.info("Persistent menu button configured.")

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
        trip_details = ""
        if summary.get("trip_list"):
            trip_details = "\n*Trip History*:\n"
            for i, d in enumerate(summary["trip_list"], 1):
                trip_details += f" {i}. `{d} KM`\n"

        text = (
            f"📊 *Today's Summary*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ Trips: `{summary['trips']}`\n"
            f"🛣 Total KM: `{summary['km']:.1f} KM`\n"
            f"⛽ Spent: `₹{summary['fuel']}`\n"
            f"{trip_details}"
            f"━━━━━━━━━━━━━━━━━━━━"
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
                CommandHandler("downloadrange", self.admin_handler.start_download_range),
                CommandHandler("broadcast", self.admin_handler.start_broadcast),
                CommandHandler("health", self.admin_handler.health_check),
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
                # Admin Download Range
                ADMIN_DL_FROM: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.admin_handler.handle_from_date)],
                ADMIN_DL_TO: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.admin_handler.handle_to_date)],
                # Admin Broadcast
                ADMIN_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.admin_handler.handle_broadcast)],
            },
            fallbacks=[
                CommandHandler("start", self.start),
                CommandHandler("cancel", self.cancel),
                MessageHandler(filters.Regex("^❌ Cancel$"), self.cancel),
                CommandHandler("admin", self.admin_handler.admin_menu),
            ],
            allow_reentry=True,
            name="fleet_conv",
            persistent=True,
        )

        # Admin Commands (Priority)
        application.add_handler(CommandHandler("admin", self.admin_handler.admin_menu))
        application.add_handler(CommandHandler("viewdaily", self.admin_handler.view_daily_stats))
        application.add_handler(CommandHandler("viewweekly", self.admin_handler.view_daily_stats))
        application.add_handler(CommandHandler("viewfuel", self.admin_handler.view_fuel_stats))
        application.add_handler(CommandHandler("viewdrivers", self.admin_handler.view_drivers))
        application.add_handler(CommandHandler("live", self.admin_handler.view_live_status))
        application.add_handler(CommandHandler("gallery", self.admin_handler.view_recent_gallery))
        application.add_handler(CommandHandler("downloadtoday", self.admin_handler.download_today))
        application.add_handler(CommandHandler("downloadweekly", self.admin_handler.download_weekly))
        application.add_handler(CommandHandler("downloadrange", self.admin_handler.start_download_range))
        application.add_handler(CommandHandler("downloadphotos", self.admin_handler.download_photos))

        # Admin Callbacks (Generic)
        application.add_handler(
            CallbackQueryHandler(
                self.admin_handler.handle_admin_callback, pattern="^(refresh_|drv_|back_|approve_|reject_)"
            )
        )

        application.add_handler(conv_handler)

        application.run_polling()


if __name__ == "__main__":
    FleetBot().run()
