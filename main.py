import asyncio
import time

from utils.db.db import (
    db_init,
    get_tasks,
    task_deletion_scheduler,
    get_user_settings,
    toggle_description_optional,
    toggle_reminder_optional,
    reminder_scheduler,
    update_reminder_time,
    notification_scheduler,
    get_notifications,
    insert_task,
    get_single_task,
    update_task_status,
    set_task_name,
    insert_notification,
    get_single_notification,
    update_notification,
    disable_notification,
)
from states import TaskStates, ReminderStates, NotificationStates
from menus import startMenu, cancel_markup
from utils.dynamic_keyboard import generate_settings_menu
from pytz import timezone


import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    CallbackQuery,
)

from datetime import datetime, timedelta


load_dotenv()

# bot init
bot = Bot(token=os.getenv("TOKEN"))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# start
@dp.message(Command("start"))
async def start_command(message: Message):
    await message.answer("Menu:", reply_markup=startMenu)


# settings
@dp.message(Command("settings"))
@dp.message(lambda message: message.text == "Settings ⚙️")
async def show_settings(message: Message):
    settings_menu = await generate_settings_menu(message.from_user.id)
    await message.answer("Settings:", reply_markup=settings_menu)


@dp.message(Command("back"))
@dp.message(lambda message: message.text == "Back 🔙")
async def go_back_to_main_menu(message: Message):
    await message.answer("Menu:", reply_markup=startMenu)


@dp.message(
    lambda message: message.text
    in ["Turn on tasks descriptions 📖", "Turn off tasks descriptions 📖"]
)
async def toggle_description(message: Message):
    new_setting = await toggle_description_optional(message.from_user.id)
    status = "OFF" if new_setting == 1 else "ON"
    await message.answer(f"Descriptions are {status} now.")

    settings_menu = await generate_settings_menu(message.from_user.id)
    await message.answer("Settings:", reply_markup=settings_menu)


@dp.message(
    lambda message: message.text
    in ["Turn on tasks reminder ⏰", "Turn off tasks reminder ⏰"]
)
async def toggle_reminder(message: Message, state: FSMContext):
    new_setting = await toggle_reminder_optional(message.from_user.id)
    status = "ON" if new_setting == 1 else "OFF"
    await message.answer(f"Reminder is {status} now.")

    settings_menu = await generate_settings_menu(message.from_user.id)
    await message.answer("Settings:", reply_markup=settings_menu)

    if new_setting == 1:
        await message.answer("Please send reminder time (HH:MM, Moscow time).")
        await state.set_state(ReminderStates.waiting_for_reminder_time)


@dp.message(ReminderStates.waiting_for_reminder_time)
async def set_reminder_time(message: Message, state: FSMContext):
    reminder_time = message.text

    # time validation
    try:
        time.strptime(reminder_time, "%H:%M")
    except ValueError:
        await message.answer("Invalid format. Please send in HH:MM format.")
        return

    await update_reminder_time(message.from_user.id, reminder_time)
    await message.answer(f"Reminder set for {reminder_time} daily.")
    await state.clear()


# add task
@dp.message(Command("add_task"))
@dp.message(lambda message: message.text == "Add task ➕")
async def init_add_task(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Send me the task!", reply_markup=cancel_markup)
    await state.set_state(TaskStates.waiting_for_task_name)


@dp.message(TaskStates.waiting_for_task_name)
async def add_task_name(message: Message, state: FSMContext):
    await state.update_data(task_name=message.text)
    user_settings = await get_user_settings(message.from_user.id)
    description_optional = user_settings["description_optional"]

    if description_optional:
        await insert_task(message.from_user.id, message.text, "")
        await message.answer("Task added successfully!")
        await state.clear()
    else:
        await message.answer("Now send me description!", reply_markup=cancel_markup)
        await state.set_state(TaskStates.waiting_for_task_description)


@dp.message(TaskStates.waiting_for_task_description)
async def add_task_description(message: Message, state: FSMContext):
    data = await state.get_data()
    await insert_task(message.from_user.id, data["task_name"], message.text)
    await message.answer("Task added successfully!")
    await state.clear()


# view task - displays task name and description (or placeholder if empty)
@dp.message(Command("show_tasks"))
@dp.message(lambda message: message.text == "Show tasks 📋")
async def show_tasks(message: Message):
    tasks = await get_tasks(message.from_user.id)
    if not tasks:
        await message.answer("You have no tasks yet.")
        return

    inline_keyboard = []
    for task in tasks:
        task_id, task_name, task_description, status = task
        task_button = InlineKeyboardButton(
            text=f"{task_name}", callback_data=f"view_task_{task_id}"
        )
        edit_button = InlineKeyboardButton(
            text="✏️ Edit", callback_data=f"edit_task_{task_id}"
        )
        complete_button = InlineKeyboardButton(
            text="✅ Complete", callback_data=f"complete_task_{task_id}"
        )
        inline_keyboard.append([task_button, edit_button, complete_button])

    keyboard = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
    await message.answer("Your tasks:", reply_markup=keyboard)


@dp.callback_query(lambda c: c.data and c.data.startswith("edit_task_"))
async def edit_task(callback_query: CallbackQuery, state: FSMContext):
    task_id = callback_query.data.split("_")[2]
    task = await get_single_task(task_id)

    if task:
        await state.update_data(task_id=task_id)
        await callback_query.message.answer(
            f"Current task name: {task[0]}\nPlease send a new task name."
        )
        await state.set_state(TaskStates.waiting_for_task_edit)
    else:
        await callback_query.message.answer("Task not found.")
    await callback_query.answer()


@dp.message(TaskStates.waiting_for_task_edit)
async def save_edited_task(message: Message, state: FSMContext):
    data = await state.get_data()
    task_id = data["task_id"]
    new_task_name = message.text

    await set_task_name(task_id, new_task_name)
    await message.answer(f"Task updated to: {new_task_name}")
    await state.clear()


# complete task - marks task as complete/incomplete and updates button status
@dp.callback_query(lambda c: c.data and c.data.startswith("complete_task_"))
async def complete_task(callback_query: CallbackQuery):
    task_id = callback_query.data.split("_")[2]
    task = await get_single_task(task_id)

    if task:
        task_name, _, current_status = task
        new_status = 1 if current_status == 0 else 0
        await update_task_status(task_id, new_status)
        await callback_query.message.edit_reply_markup(reply_markup=None)
        await callback_query.message.answer(
            f"""Task '{task_name}' marked as {'completed' if new_status == 1 else 
                                            'incomplete'}."""
        )
    else:
        await callback_query.answer("Task not found.")


@dp.callback_query(lambda c: c.data and c.data.startswith("view_task_"))
async def view_task(callback_query):
    task_id = callback_query.data.split("_")[2]
    task = await get_single_task(task_id)
    if task:
        name, description, _ = task
        await callback_query.message.answer(f"{name}\n{description}\n")
    else:
        await callback_query.message.answer("Task not found.")
    await callback_query.answer()


# Notifications
@dp.message(lambda message: message.text == "Add notification ⏰")
async def init_add_notification(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Send me the notification name.", reply_markup=cancel_markup)
    await state.set_state(NotificationStates.waiting_for_notification_name)


@dp.message(NotificationStates.waiting_for_notification_name)
async def set_notification_name(message: Message, state: FSMContext):
    notification_name = message.text
    await state.update_data(notification_name=notification_name)

    await message.answer(
        "Please send me the time in HH:MM format or choose one of the presets:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text="In 1 hour"),
                    KeyboardButton(text="10:00"),
                    KeyboardButton(text="14:00"),
                    KeyboardButton(text="18:00"),
                ],
                [KeyboardButton(text="Отмена 🛇")],
            ],
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )
    await state.set_state(NotificationStates.waiting_for_notification_time)


@dp.message(NotificationStates.waiting_for_notification_time)
async def set_notification_time(message: Message, state: FSMContext):
    data = await state.get_data()
    if message.text.lower() == "in 1 hour":
        notification_time = (datetime.now() + timedelta(hours=1)).strftime("%H:%M")
        notification_date = (datetime.now() + timedelta(hours=1)).strftime("%d.%m.%Y")
        await state.update_data(
            notification_time=notification_time, notification_date=notification_date
        )
        await insert_notification(
            message.from_user.id,
            data["notification_name"],
            notification_date,
            notification_time,
        )
        await message.answer(
            f"Reminder '{data['notification_name']}' set for {notification_date}"
            f" at {notification_time}",
            reply_markup=startMenu,
        )
        await state.clear()
    elif message.text.lower() == "отмена 🛇":
        await state.clear()
        await message.answer("Cancelled!", reply_markup=startMenu)
    else:
        try:
            time_object = time.strptime(message.text, "%H:%M")
            notification_time = time.strftime("%H:%M", time_object)
            await state.update_data(notification_time=notification_time)
            await message.answer(
                "Please send me the date in DD.MM format or choose from presets:",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[
                        [
                            KeyboardButton(text="Tomorrow"),
                            KeyboardButton(text="In 3 days"),
                            KeyboardButton(text="Next week"),
                        ],
                        [KeyboardButton(text="Отмена 🛇")],
                    ],
                    resize_keyboard=True,
                    one_time_keyboard=True,
                ),
            )
            await state.set_state(NotificationStates.waiting_for_notification_date)
        except ValueError:
            await message.answer(
                "Invalid time format. Please enter in HH:MM format or choose a preset."
            )


@dp.message(NotificationStates.waiting_for_notification_date)
async def set_notification_date(message: Message, state: FSMContext):
    if message.text.lower() == "отмена 🛇":
        await state.clear()
        await message.answer("Cancelled!", reply_markup=startMenu)
        return

    moscow_tz = timezone("Europe/Moscow")
    now = datetime.now(moscow_tz)

    data = await state.get_data()
    reminder_time = data.get("notification_time", "00:00")

    if message.text.lower() == "tomorrow":
        notification_date = (now + timedelta(days=1)).strftime("%d.%m.%Y")
    elif message.text.lower() == "in 3 days":
        notification_date = (now + timedelta(days=3)).strftime("%d.%m.%Y")
    elif message.text.lower() == "next week":
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
            await message.answer(
                "Invalid date format. Please enter in DD.MM format or choose a preset."
            )
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
        f"""
        Reminder '{data['notification_name']}' set for {notification_date}
        at {data['notification_time']}
        """.replace('\n', ' ').strip(),
        reply_markup=startMenu,
    )
    await state.clear()


@dp.message(lambda message: message.text == "Show notifications 📅")
async def show_notifications(message: Message):
    notifications = await get_notifications(message.from_user.id)

    if not notifications:
        await message.answer("You have no active notifications.")
        return

    inline_keyboard = []
    for notification in notifications:
        notification_id, name, date, time = notification

        edit_button = InlineKeyboardButton(
            text="✏️ Edit", callback_data=f"edit_notification_{notification_id}"
        )
        complete_button = InlineKeyboardButton(
            text="✅ Complete",
            callback_data=f"complete_notification_{notification_id}",
        )

        notification_button = InlineKeyboardButton(
            text=f"{name} | {date} | {time}",
            callback_data=f"view_notification_{notification_id}",
        )

        inline_keyboard.append([notification_button, edit_button, complete_button])

    keyboard = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

    await message.answer("Your notifications:", reply_markup=keyboard)


@dp.callback_query(lambda c: c.data and c.data.startswith("view_notification_"))
async def view_notification(callback_query):
    notification_id = callback_query.data.split("_")[2]
    notification = await get_single_notification(notification_id)

    if notification:
        name, date, time = notification
        await callback_query.message.answer(f"{name}\n{date}\n{time}")
    else:
        await callback_query.message.answer("Notification not found.")

    await callback_query.answer()


@dp.callback_query(lambda c: c.data and c.data.startswith("complete_notification_"))
async def complete_notification(callback_query):
    notification_id = callback_query.data.split("_")[2]
    await disable_notification(notification_id)

    await callback_query.message.answer("Notification completed.")
    await callback_query.answer()


@dp.callback_query(lambda c: c.data and c.data.startswith("edit_notification_"))
async def edit_notification(callback_query, state: FSMContext):
    notification_id = callback_query.data.split("_")[2]
    notification = await get_single_notification(notification_id)

    if notification:
        await state.update_data(notification_id=notification_id)
        await callback_query.message.answer(
            f"Current notification name: {notification[0]}\n"
            "Please send me the new date in DD.MM format or choose from presets:",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[
                    [
                        KeyboardButton(text="Tomorrow"),
                        KeyboardButton(text="In 3 days"),
                        KeyboardButton(text="Next week"),
                    ]
                ],
                resize_keyboard=True,
                one_time_keyboard=True,
            ),
        )
        await state.set_state(NotificationStates.waiting_for_notification_edit_date)
    else:
        await callback_query.message.answer("Notification not found.")
    await callback_query.answer()


@dp.message(NotificationStates.waiting_for_notification_edit_date)
async def edit_notification_date(message: Message, state: FSMContext):
    if message.text.lower() == "tomorrow":
        notification_date = (datetime.now() + timedelta(days=1)).strftime("%d.%m.%Y")
    elif message.text.lower() == "in 3 days":
        notification_date = (datetime.now() + timedelta(days=3)).strftime("%d.%m.%Y")
    elif message.text.lower() == "next week":
        notification_date = (datetime.now() + timedelta(days=7)).strftime("%d.%m.%Y")
    else:
        try:
            notification_date = datetime.strptime(message.text, "%d.%m").replace(
                year=datetime.now().year
            )
            notification_date = notification_date.strftime("%d.%m.%Y")
        except ValueError:
            await message.answer(
                "Invalid date format. Please enter in DD.MM format or choose a preset."
            )
            return

    await state.update_data(notification_date=notification_date)

    await message.answer(
        "Please send me the new time in HH:MM format or choose one of the presets:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text="10:00"),
                    KeyboardButton(text="14:00"),
                    KeyboardButton(text="18:00"),
                ]
            ],
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )
    await state.set_state(NotificationStates.waiting_for_notification_edit_time)


@dp.message(NotificationStates.waiting_for_notification_edit_time)
async def edit_notification_time(message: Message, state: FSMContext):
    if message.text in ["10:00", "14:00", "18:00"]:
        notification_time = message.text
    else:
        try:
            time_object = time.strptime(message.text, "%H:%M")
            notification_time = time.strftime("%H:%M", time_object)
        except ValueError:
            await message.answer(
                "Invalid time format. Please enter in HH:MM format or choose a preset."
            )
            return

    data = await state.get_data()

    await update_notification(
        data["notification_id"], data["notification_date"], notification_time
    )

    await message.answer(
        f"Notification updated to {data['notification_date']} at {notification_time}",
        reply_markup=startMenu,
    )
    await state.clear()


@dp.callback_query(lambda c: c.data == "cancel_action")
async def cancel_action(callback_query: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback_query.message.answer("Cancelled!", reply_markup=startMenu)
    await callback_query.answer()


async def on_startup():
    await db_init()
    print("Database initialized")


async def main():
    await on_startup()
    loop = asyncio.get_running_loop()
    loop.create_task(task_deletion_scheduler())
    loop.create_task(reminder_scheduler(bot))
    loop.create_task(notification_scheduler(bot))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
