import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import aiosqlite
import asyncio

from db import DB_FILE, db_init, get_tasks, task_deletion_scheduler, get_user_settings, toggle_description_optional
from states import TaskStates
from menus import startMenu, settingsMenu

load_dotenv()

# bot init
bot = Bot(token=os.getenv("TOKEN"))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# start
@dp.message(Command("start"))
async def start_command(message: Message):
    await message.answer("Menu:", reply_markup=startMenu)


# add task
@dp.message(Command("add_task"))
@dp.message(lambda message: message.text == "Add task")
async def init_add_task(message: Message, state: FSMContext):
    await message.answer("Send me the task!")
    await state.set_state(TaskStates.waiting_for_task_name)


@dp.message(TaskStates.waiting_for_task_name)
async def add_task_name(message: Message, state: FSMContext):
    await state.update_data(task_name=message.text)

    description_optional = await get_user_settings(message.from_user.id)

    if description_optional: 
        task_name = message.text

        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute(
                "INSERT INTO tasks (user_id, task, description) VALUES (?, ?, ?)",
                (message.from_user.id, task_name, "") 
            )
            await db.commit()

        await message.answer("Task added successfully!")
        await state.clear()  
    else:
        await message.answer("Now send me description! Send '-' to skip this part.")
        await state.set_state(TaskStates.waiting_for_task_description)



@dp.message(TaskStates.waiting_for_task_description)
async def add_task_description(message: Message, state: FSMContext):
    data = await state.get_data()
    task_name = data['task_name']
    task_description = message.text

    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "INSERT INTO tasks (user_id, task, description) VALUES (?, ?, ?)",
            (message.from_user.id, task_name, task_description)
        )
        await db.commit()

    await message.answer("Task added successfully!")
    await state.clear()


# settings
@dp.message(Command("settings"))
@dp.message(lambda message: message.text == "Settings")
async def show_settings(message: Message):
    await message.answer("Settings:", reply_markup=settingsMenu)

# description_setting
@dp.message(Command("toggle description settings"))
@dp.message(lambda message: message.text == "Toggle tasks descriptions")
async def toggle_description(message: Message):
    new_setting = await toggle_description_optional(message.from_user.id)
    status = "OFF" if new_setting == 1 else "ON"
    await message.answer(f"Descriptions are {status} now.")

# show tasks
@dp.message(Command("show_tasks"))
@dp.message(lambda message: message.text == "Show tasks")
async def show_tasks(message: Message):
    tasks = await get_tasks(message.from_user.id)

    if not tasks:
        await message.answer("You have no tasks yet.")
        return

    inline_keyboard = []

    for task in tasks:
        task_id, task_name, _, status = task
        status_emoji = "❌" if status == 0 else "✅"

        task_button = InlineKeyboardButton(
            text=f"{task_name}",
            callback_data=f"view_{task_id}"
        )
        complete_button = InlineKeyboardButton(
            text=status_emoji,
            callback_data=f"complete_{task_id}"
        )

        inline_keyboard.append([task_button, complete_button])

    keyboard = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

    await message.answer("Your tasks:", reply_markup=keyboard)


async def process_view_task(callback_query):
    task_id = callback_query.data.split("_")[1]
    async with aiosqlite.connect(DB_FILE) as db:
        task = await db.execute_fetchall("SELECT description FROM tasks WHERE id = ?", (task_id,))
    
    if task:
        await callback_query.message.answer(f"Description: {task[0][0]}")
    else:
        await callback_query.message.answer("Task cannot be found.")


async def process_complete_task(callback_query):
    task_id = callback_query.data.split("_")[1]
    
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT task, status FROM tasks WHERE id = ?", (task_id,)) as cursor:
            task = await cursor.fetchone()

        if task:
            task_name, current_status = task
            new_status = 1 if current_status == 0 else 0
            await db.execute("UPDATE tasks SET status = ? WHERE id = ?", (new_status, task_id))
            await db.commit()

    status_emoji = "✅" if new_status == 1 else "❌"
    task_button = InlineKeyboardButton(
        text=f"{task_name}",
        callback_data=f"view_{task_id}"
    )
    complete_button = InlineKeyboardButton(
        text=status_emoji,
        callback_data=f"complete_{task_id}"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[[task_button, complete_button]])

    await callback_query.message.edit_text(f"Your tasks:", reply_markup=keyboard)
    await callback_query.answer()


dp.callback_query.register(process_view_task, lambda c: c.data and c.data.startswith("view_"))
dp.callback_query.register(process_complete_task, lambda c: c.data and c.data.startswith("complete_"))





async def on_startup():
    await db_init()
    print("Database initialized")

async def main():
    await on_startup()
    loop = asyncio.get_running_loop()
    loop.create_task(task_deletion_scheduler())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
