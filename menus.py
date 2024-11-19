from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
import gettext


def setup_locales(locale: str = "en"):
    lang = gettext.translation(
        "bot", localedir="locales", languages=[locale], fallback=True
    )
    lang.install()
    return lang.gettext


_ = setup_locales(locale="ru")

startMenu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text=_("add_task_button")),
            KeyboardButton(text=_("show_tasks_button")),
        ],
        [
            KeyboardButton(text=_("add_notification_button")),
            KeyboardButton(text=_("show_notifications_button")),
        ],
        [
            KeyboardButton(text=_("settings_button")),
        ],
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
    input_field_placeholder=_("menu_placeholder"),
)

cancel_button = InlineKeyboardButton(
    text=_("cancel_button"), callback_data="cancel_action"
)
cancel_markup = InlineKeyboardMarkup(inline_keyboard=[[cancel_button]])
