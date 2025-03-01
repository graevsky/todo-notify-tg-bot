from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from utils.db.db import get_user_settings
import gettext


async def generate_settings_menu(user_id):
    user_settings = await get_user_settings(user_id)
    description_optional = user_settings["description_optional"]
    reminder_optional = user_settings["reminder_optional"]

    description_text = (
        "Turn on tasks descriptions 📖"
        if description_optional
        else "Turn off tasks descriptions 📖"
    )
    reminder_text = (
        "Turn off tasks reminder ⏰"
        if reminder_optional
        else "Turn on tasks reminder ⏰"
    )

    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=description_text), KeyboardButton(text=reminder_text)],
            [KeyboardButton(text="Back 🔙")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="Settings",
    )
