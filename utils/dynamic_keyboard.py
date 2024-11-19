from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from utils.db.db import get_user_settings
import gettext


def setup_locales(locale: str = "en"):
    lang = gettext.translation(
        "bot", localedir="locales", languages=[locale], fallback=True
    )
    lang.install()
    return lang.gettext


_ = setup_locales(locale="ru")


async def generate_settings_menu(user_id):
    user_settings = await get_user_settings(user_id)
    description_optional = user_settings["description_optional"]
    reminder_optional = user_settings["reminder_optional"]

    description_text = (
        _("turn_on_descriptions")
        if description_optional
        else _("turn_off_descriptions")
    )
    reminder_text = (
        _("turn_off_reminder") if reminder_optional else _("turn_on_reminder")
    )

    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=description_text), KeyboardButton(text=reminder_text)],
            [KeyboardButton(text=_("back_button"))],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder=_("settings_placeholder"),
    )
