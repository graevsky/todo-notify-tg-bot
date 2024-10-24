from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
)

startMenu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="Show tasks 📋"),
            KeyboardButton(text="Add task ➕"),
            KeyboardButton(text="Settings ⚙️"),
        ]
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
    input_field_placeholder="Menu",
)

settingsMenu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="Toggle tasks descriptions 📖"),
            KeyboardButton(text="Toggle tasks reminder ⏰"),
        ],
        [KeyboardButton(text="Back 🔙")],
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
    input_field_placeholder="Settings",
)
