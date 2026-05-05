from telegram import ReplyKeyboardMarkup

def get_main_menu():
    return ReplyKeyboardMarkup(
        [
            ["🚗 Start Trip", "🛑 End Trip"],
            ["📊 Today Summary", "🏆 Leaderboard"],
            ["⚠️ Report Damage", "👤 Profile"],
            ["❌ Cancel"]
        ],
        resize_keyboard=True
    )
