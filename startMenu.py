from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, KeyboardButton, InlineKeyboardButton

startMenu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="Show tasks"),
            KeyboardButton(text="Add task")
        ]
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
    input_field_placeholder="Menu"
)