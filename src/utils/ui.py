from telegram import KeyboardButton, ReplyKeyboardMarkup


def get_main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Returns the primary navigation keyboard."""
    keyboard: list[list[KeyboardButton]] = [
        [KeyboardButton("🚗 Start Trip"), KeyboardButton("🛑 End Trip")],
        [KeyboardButton("🌅 Start Bulk Day"), KeyboardButton("🌃 End Bulk Day")],
        [KeyboardButton("📊 Today Summary"), KeyboardButton("🏆 Leaderboard")],
        [KeyboardButton("👤 Profile"), KeyboardButton("⚠️ Report Damage")],
    ]
    if is_admin:
        keyboard.append([KeyboardButton("👨‍✈️ Admin Panel")])

    keyboard.append([KeyboardButton("❌ Cancel")])

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
