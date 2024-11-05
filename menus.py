from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

startMenu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="Add task ➕"),
            KeyboardButton(text="Show tasks 📋"),
        ],
        [
            KeyboardButton(text="Add notification ⏰"),
            KeyboardButton(text="Show notifications 📅"),
        ],
        [
            KeyboardButton(text="Settings ⚙️"),
        ],
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
    input_field_placeholder="Menu",
)

cancel_button = InlineKeyboardButton(text="Отмена 🛇", callback_data="cancel_action")
cancel_markup = InlineKeyboardMarkup(inline_keyboard=[[cancel_button]])
