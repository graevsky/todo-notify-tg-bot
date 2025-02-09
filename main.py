import asyncio
import gettext
import os
import time
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from dotenv import load_dotenv
from pytz import timezone

from menus import cancel_markup, startMenu
from states import MainStates, NotificationStates, ReminderStates, TaskStates
from utils.db.db import (
    db_init,
    disable_notification,
    get_notifications,
    get_single_notification,
    get_single_task,
    get_tasks,
    get_user_settings,
    insert_notification,
    insert_task,
    notification_scheduler,
    reminder_scheduler,
    set_task_name,
    task_deletion_scheduler,
    toggle_description_optional,
    toggle_reminder_optional,
    update_notification,
    update_reminder_time,
    update_task_status,
)
from utils.dynamic_keyboard import generate_settings_menu

load_dotenv()


def setup_locales(locale: str = "en"):
    lang = gettext.translation("bot", localedir="locales", languages=[locale], fallback=True)
    lang.install()
    return lang.gettext


_ = setup_locales(locale="ru")

# bot init
bot = Bot(token=os.getenv("TOKEN"))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# start
@dp.message(Command("start"))
async def start_command(message: Message):
    await message.answer(_("menu_title"), reply_markup=startMenu)


# settings
@dp.message(Command("settings"))
@dp.message(lambda message: message.text == _("settings_button"))
async def show_settings(message: Message):
    settings_menu = await generate_settings_menu(message.from_user.id)
    await message.answer(_("settings"), reply_markup=settings_menu)


@dp.message(Command("back"))
@dp.message(lambda message: message.text == _("back_button"))
async def go_back_to_main_menu(message: Message):
    await message.answer(_("menu_title"), reply_markup=startMenu)


@dp.message(lambda message: message.text in [_("turn_on_descriptions"), _("turn_off_descriptions")])
async def toggle_description(message: Message):
    new_setting = await toggle_description_optional(message.from_user.id)
    status = _("off") if new_setting == 1 else _("on")
    await message.answer(_("description_status").format(status=status))

    settings_menu = await generate_settings_menu(message.from_user.id)
    await message.answer(_("settings"), reply_markup=settings_menu)


@dp.message(lambda message: message.text in [_("turn_on_reminder"), _("turn_off_reminder")])
async def toggle_reminder(message: Message, state: FSMContext):
    new_setting = await toggle_reminder_optional(message.from_user.id)
    status = _("on") if new_setting == 1 else _("off")
    await message.answer(_("reminder_status").format(status=status))

    settings_menu = await generate_settings_menu(message.from_user.id)
    await message.answer(_("settings"), reply_markup=settings_menu)

    if new_setting == 1:
        await message.answer(_("send_reminder_time"))
        await state.set_state(ReminderStates.waiting_for_reminder_time)


@dp.message(ReminderStates.waiting_for_reminder_time)
async def set_reminder_time(message: Message, state: FSMContext):
    reminder_time = message.text

    # time validation
    try:
        time.strptime(reminder_time, "%H:%M")
    except ValueError:
        await message.answer(_("invalid_time_format"))
        return

    await update_reminder_time(message.from_user.id, reminder_time)
    await message.answer(_("reminder_set").format(reminder_time=reminder_time))
    await state.set_state(MainStates.main_state)


# add task
@dp.message(Command("add_task"))
@dp.message(lambda message: message.text == _("add_task_button"))
async def init_add_task(message: Message, state: FSMContext):
    await state.set_state(MainStates.main_state)
    await message.answer(_("send_task_name"), reply_markup=cancel_markup)
    await state.set_state(TaskStates.waiting_for_task_name)


# KB complete
@dp.message(Command("complete"), state=MainStates.main_state)
async def kb_complete_task(message: Message):
    # Get task_id from command arguments
    try:
        task_id = message.text.split()[1]
    except IndexError:
        await message.answer(_("task_not_found"))
        return

    task = await get_single_task(task_id)

    if task:
        task_name, _desc, current_status = task
        new_status = 1 if current_status == 0 else 0
        await update_task_status(task_id, new_status)
        await message.edit_reply_markup(reply_markup=None)
        await message.answer(
            _("task_marked").format(
                task_name=task_name,
                status=_("completed") if new_status == 1 else _("incomplete"),
            )
        )
    else:
        await message.answer(_("task_not_found"))


@dp.message(TaskStates.waiting_for_task_name)
async def add_task_name(message: Message, state: FSMContext):
    await state.update_data(task_name=message.text)
    user_settings = await get_user_settings(message.from_user.id)
    description_optional = user_settings["description_optional"]

    if description_optional:
        await insert_task(message.from_user.id, message.text, "")
        await message.answer(_("task_added_success"), reply_markup=startMenu)
        await state.set_state(MainStates.main_state)
    else:
        await message.answer(_("send_task_description"), reply_markup=cancel_markup)
        await state.set_state(TaskStates.waiting_for_task_description)


@dp.message(TaskStates.waiting_for_task_description)
async def add_task_description(message: Message, state: FSMContext):
    data = await state.get_data()
    await insert_task(message.from_user.id, data["task_name"], message.text)
    await message.answer(_("task_added_success"), reply_markup=startMenu)
    await state.set_state(MainStates.main_state)


# view task - displays task name and description (or placeholder if empty)
@dp.message(Command("show_tasks"))
@dp.message(lambda message: message.text == _("show_tasks_button"))
async def show_tasks(message: Message):
    tasks = await get_tasks(message.from_user.id)
    if not tasks:
        await message.answer(_("no_tasks"))
        return

    inline_keyboard = []
    for task in tasks:
        task_id, task_name, task_description, status = task
        task_button = InlineKeyboardButton(text=f"{task_name}", callback_data=f"view_task_{task_id}")
        edit_button = InlineKeyboardButton(text=_("edit_button"), callback_data=f"edit_task_{task_id}")
        complete_button = InlineKeyboardButton(text=_("complete_button"), callback_data=f"complete_task_{task_id}")
        inline_keyboard.append([task_button, edit_button, complete_button])

    keyboard = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
    await message.answer(_("your_tasks"), reply_markup=keyboard)


@dp.callback_query(lambda c: c.data and c.data.startswith("edit_task_"))
async def edit_task(callback_query: CallbackQuery, state: FSMContext):
    task_id = callback_query.data.split("_")[2]
    task = await get_single_task(task_id)

    if task:
        await state.update_data(task_id=task_id)
        await callback_query.message.answer(_("current_task_name").format(task_name=task[0]))
        await state.set_state(TaskStates.waiting_for_task_edit)
    else:
        await callback_query.message.answer(_("task_not_found"))
    await callback_query.answer()


@dp.message(TaskStates.waiting_for_task_edit)
async def save_edited_task(message: Message, state: FSMContext):
    data = await state.get_data()
    task_id = data["task_id"]
    new_task_name = message.text

    await set_task_name(task_id, new_task_name)
    await message.answer(_("task_updated").format(task_name=new_task_name))
    await state.set_state(MainStates.main_state)


# complete task - marks task as complete/incomplete and updates button status
@dp.callback_query(lambda c: c.data and c.data.startswith("complete_task_"))
async def complete_task(callback_query: CallbackQuery):
    task_id = callback_query.data.split("_")[2]
    task = await get_single_task(task_id)

    if task:
        task_name, _desc, current_status = task
        new_status = 1 if current_status == 0 else 0
        await update_task_status(task_id, new_status)
        await callback_query.message.edit_reply_markup(reply_markup=None)
        await callback_query.message.answer(
            _("task_marked").format(
                task_name=task_name,
                status=_("completed") if new_status == 1 else _("incomplete"),
            )
        )
    else:
        await callback_query.answer(_("task_not_found"))


# from here
@dp.callback_query(lambda c: c.data and c.data.startswith("view_task_"))
async def view_task(callback_query):
    task_id = callback_query.data.split("_")[2]
    task = await get_single_task(task_id)
    if task:
        name, description, _status = task
        await callback_query.message.answer(f"{name}\n{description}\n")
    else:
        await callback_query.message.answer(_("task_not_found"))
    await callback_query.answer()


# Notifications
@dp.message(lambda message: message.text == _("add_notification_button"))
async def init_add_notification(message: Message, state: FSMContext):
    await state.set_state(MainStates.main_state)
    await message.answer(_("send_notification_name"), reply_markup=cancel_markup)
    await state.set_state(NotificationStates.waiting_for_notification_name)


@dp.message(NotificationStates.waiting_for_notification_name)
async def set_notification_name(message: Message, state: FSMContext):
    notification_name = message.text
    await state.update_data(notification_name=notification_name)

    await message.answer(
        _("send_notification_time"),
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text=_("preset_in_1_hour")),
                    KeyboardButton(text="10:00"),
                    KeyboardButton(text="14:00"),
                    KeyboardButton(text="18:00"),
                ],
                [KeyboardButton(text=_("cancel_button"))],
            ],
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )
    await state.set_state(NotificationStates.waiting_for_notification_time)


@dp.message(NotificationStates.waiting_for_notification_time)
async def set_notification_time(message: Message, state: FSMContext):
    data = await state.get_data()
    if message.text.lower() == _("preset_in_1_hour").lower():
        notification_time = (datetime.now() + timedelta(hours=1)).strftime("%H:%M")
        notification_date = (datetime.now() + timedelta(hours=1)).strftime("%d.%m.%Y")
        await state.update_data(notification_time=notification_time, notification_date=notification_date)
        await insert_notification(
            message.from_user.id,
            data["notification_name"],
            notification_date,
            notification_time,
        )
        await message.answer(
            _("notification_set").format(
                name=data["notification_name"],
                date=notification_date,
                time=notification_time,
            ),
            reply_markup=startMenu,
        )
        await state.set_state(MainStates.main_state)
    elif message.text.lower() == _("cancel_button").lower():
        await state.set_state(MainStates.main_state)
        await message.answer(_("cancelled"), reply_markup=startMenu)
    else:
        try:
            time_object = time.strptime(message.text, "%H:%M")
            notification_time = time.strftime("%H:%M", time_object)
            await state.update_data(notification_time=notification_time)
            await message.answer(
                _("send_notification_date"),
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[
                        [
                            KeyboardButton(text=_("preset_tomorrow")),
                            KeyboardButton(text=_("preset_in_3_days")),
                            KeyboardButton(text=_("preset_next_week")),
                        ],
                        [KeyboardButton(text=_("cancel_button"))],
                    ],
                    resize_keyboard=True,
                    one_time_keyboard=True,
                ),
            )
            await state.set_state(NotificationStates.waiting_for_notification_date)
        except ValueError:
            await message.answer(_("invalid_time_format"))


@dp.message(NotificationStates.waiting_for_notification_date)
async def set_notification_date(message: Message, state: FSMContext):
    if message.text.lower() == _("cancel_button").lower():
        await state.set_state(MainStates.main_state)
        await message.answer(_("cancelled"), reply_markup=startMenu)
        return

    moscow_tz = timezone("Europe/Moscow")
    now = datetime.now(moscow_tz)

    data = await state.get_data()
    reminder_time = data.get("notification_time", "00:00")

    if message.text.lower() == _("preset_tomorrow").lower():
        notification_date = (now + timedelta(days=1)).strftime("%d.%m.%Y")
    elif message.text.lower() == _("preset_in_3_days").lower():
        notification_date = (now + timedelta(days=3)).strftime("%d.%m.%Y")
    elif message.text.lower() == _("preset_next_week").lower():
        notification_date = (now + timedelta(days=7)).strftime("%d.%m.%Y")
    else:
        try:
            input_date = datetime.strptime(message.text, "%d.%m").replace(year=now.year)
            reminder_time_object = datetime.strptime(reminder_time, "%H:%M").time()

            input_date = datetime.combine(input_date, reminder_time_object)
            input_date = moscow_tz.localize(input_date)

            if input_date < now:
                input_date = input_date.replace(year=now.year + 1)

            notification_date = input_date.strftime("%d.%m.%Y")
        except ValueError:
            await message.answer(_("invalid_date_format"))
            return

    await state.update_data(notification_date=notification_date)
    data = await state.get_data()
    await insert_notification(
        message.from_user.id,
        data["notification_name"],
        notification_date,
        data["notification_time"],
    )

    await message.answer(
        _("notification_set").format(
            name=data["notification_name"],
            date=notification_date,
            time=data["notification_time"],
        ),
        reply_markup=startMenu,
    )
    await state.set_state(MainStates.main_state)


@dp.message(lambda message: message.text == _("show_notifications_button"))
async def show_notifications(message: Message):
    notifications = await get_notifications(message.from_user.id)

    if not notifications:
        await message.answer(_("no_notifications"))
        return

    inline_keyboard = []
    for notification in notifications:
        notification_id, name, date, time = notification

        edit_button = InlineKeyboardButton(text=_("edit_button"), callback_data=f"edit_notification_{notification_id}")
        complete_button = InlineKeyboardButton(
            text=_("complete_button"),
            callback_data=f"complete_notification_{notification_id}",
        )

        notification_button = InlineKeyboardButton(
            text=f"{name} | {date} | {time}",
            callback_data=f"view_notification_{notification_id}",
        )

        inline_keyboard.append([notification_button, edit_button, complete_button])

    keyboard = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

    await message.answer(_("your_notifications"), reply_markup=keyboard)


@dp.callback_query(lambda c: c.data and c.data.startswith("view_notification_"))
async def view_notification(callback_query):
    notification_id = callback_query.data.split("_")[2]
    notification = await get_single_notification(notification_id)

    if notification:
        name, date, time = notification
        await callback_query.message.answer(_("notification_details").format(name=name, date=date, time=time))
    else:
        await callback_query.message.answer(_("notification_not_found"))

    await callback_query.answer()


@dp.callback_query(lambda c: c.data and c.data.startswith("complete_notification_"))
async def complete_notification(callback_query: CallbackQuery):
    notification_id = callback_query.data.split("_")[2]
    notification = await get_single_notification(notification_id)

    if notification:
        await disable_notification(notification_id)
        await callback_query.message.answer(_("notification_completed"))
    else:
        await callback_query.message.answer(_("notification_not_found"))

    await callback_query.answer()


@dp.callback_query(lambda c: c.data and c.data.startswith("edit_notification_"))
async def edit_notification(callback_query, state: FSMContext):
    notification_id = callback_query.data.split("_")[2]
    notification = await get_single_notification(notification_id)

    if notification:
        await state.update_data(notification_id=notification_id)
        await callback_query.message.answer(
            _("current_notification_name").format(name=notification[0]),
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[
                    [
                        KeyboardButton(text=_("preset_tomorrow")),
                        KeyboardButton(text=_("preset_in_3_days")),
                        KeyboardButton(text=_("preset_next_week")),
                    ],
                    [KeyboardButton(text=_("cancel_button"))],
                ],
                resize_keyboard=True,
                one_time_keyboard=True,
            ),
        )
        await state.set_state(NotificationStates.waiting_for_notification_edit_date)
    else:
        await callback_query.message.answer(_("notification_not_found"))
    await callback_query.answer()


@dp.message(NotificationStates.waiting_for_notification_edit_date)
async def edit_notification_date(message: Message, state: FSMContext):
    if message.text.lower() == _("cancel_button").lower():
        await state.set_state(MainStates.main_state)
        await message.answer(_("cancelled"), reply_markup=startMenu)
        return

    now = datetime.now(timezone("Europe/Moscow"))

    if message.text.lower() == _("preset_tomorrow").lower():
        notification_date = (now + timedelta(days=1)).strftime("%d.%m.%Y")
    elif message.text.lower() == _("preset_in_3_days").lower():
        notification_date = (now + timedelta(days=3)).strftime("%d.%m.%Y")
    elif message.text.lower() == _("preset_next_week").lower():
        notification_date = (now + timedelta(days=7)).strftime("%d.%m.%Y")
    else:
        try:
            notification_date = datetime.strptime(message.text, "%d.%m").replace(year=now.year)
            if notification_date < now:
                notification_date = notification_date.replace(year=now.year + 1)
            notification_date = notification_date.strftime("%d.%m.%Y")
        except ValueError:
            await message.answer(_("invalid_date_format"))
            return

    await state.update_data(notification_date=notification_date)
    await message.answer(
        _("send_notification_new_time"),
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text="10:00"),
                    KeyboardButton(text="14:00"),
                    KeyboardButton(text="18:00"),
                ],
                [KeyboardButton(text=_("cancel_button"))],
            ],
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )
    await state.set_state(NotificationStates.waiting_for_notification_edit_time)


@dp.message(NotificationStates.waiting_for_notification_edit_time)
async def edit_notification_time(message: Message, state: FSMContext):
    if message.text.lower() == _("cancel_button").lower():
        await state.set_state(MainStates.main_state)
        await message.answer(_("cancelled"), reply_markup=startMenu)
        return

    try:
        time_object = time.strptime(message.text, "%H:%M")
        notification_time = time.strftime("%H:%M", time_object)
    except ValueError:
        await message.answer(_("invalid_time_format"))
        return

    data = await state.get_data()
    await update_notification(data["notification_id"], data["notification_date"], notification_time)

    await message.answer(
        _("notification_updated").format(date=data["notification_date"], time=notification_time),
        reply_markup=startMenu,
    )
    await state.set_state(MainStates.main_state)


@dp.callback_query(lambda c: c.data == "cancel_action")
async def cancel_action(callback_query: CallbackQuery, state: FSMContext):
    await state.set_state(MainStates.main_state)
    await callback_query.message.answer(_("cancelled"), reply_markup=startMenu)
    await callback_query.answer()


async def on_startup():
    await db_init()
    print(_("database_initialized"))


async def main():
    await on_startup()
    loop = asyncio.get_running_loop()
    loop.create_task(task_deletion_scheduler())
    loop.create_task(reminder_scheduler(bot))
    loop.create_task(notification_scheduler(bot))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
