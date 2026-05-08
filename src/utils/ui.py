from telegram import ReplyKeyboardMarkup


def get_main_menu(is_admin=False):
    keyboard = [
        ["🚗 Start Trip", "🛑 End Trip"],
        ["📊 Today Summary", "🏆 Leaderboard"],
        ["⚠️ Report Damage", "👤 Profile"],
    ]

    if is_admin:
        keyboard.append(["👨‍✈️ Admin Panel"])

    keyboard.append(["❌ Cancel"])

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
