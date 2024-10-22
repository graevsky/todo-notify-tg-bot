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

from db import DB_FILE, db_init, get_tasks
from states import TaskStates

load_dotenv()

# bot init
bot = Bot(token=os.getenv("TOKEN"))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# add task
@dp.message(Command("add_task"))
async def init_add_task(message: Message, state: FSMContext):
    await message.answer("Send me the task!")
    await state.set_state(TaskStates.waiting_for_task_name)


@dp.message(TaskStates.waiting_for_task_name)
async def add_task_name(message: Message, state: FSMContext):
    await state.update_data(task_name=message.text)
    await message.answer("Now send me description!")
    await state.set_state(TaskStates.waiting_for_task_description)


@dp.message(TaskStates.waiting_for_task_description)
async def add_task_description(message: Message, state: FSMContext):
    data = await state.get_data()
    task_name = data['task_name']
    task_description = message.text

    # Add task to DB
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "INSERT INTO tasks (user_id, task, description) VALUES (?, ?, ?)",
            (message.from_user.id, task_name, task_description)
        )
        await db.commit()

    await message.answer("Task added successfully!")
    await state.clear()


# start
@dp.message(Command("start"))
async def start_command(message: Message):
    await message.answer("Test.")


# show tasks
@dp.message(Command("show_tasks"))
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
            text=f"{task_name} {status_emoji}",
            callback_data=f"view_{task_id}"
        )
        complete_button = InlineKeyboardButton(
            text="Завершить" if status == 0 else "Восстановить",
            callback_data=f"complete_{task_id}"
        )

        inline_keyboard.append([task_button, complete_button])

    keyboard = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

    await message.answer("Ваши задания:", reply_markup=keyboard)



# Обработка нажатий на текст задания (показ описания)
async def process_view_task(callback_query):
    task_id = callback_query.data.split("_")[1]
    async with aiosqlite.connect(DB_FILE) as db:
        task = await db.execute_fetchall("SELECT description FROM tasks WHERE id = ?", (task_id,))
    
    if task:
        await callback_query.message.answer(f"Описание задания:\n{task[0]}")
    else:
        await callback_query.message.answer("Задание не найдено.")


# Обработка нажатий на крестик (завершение/восстановление задания)
async def process_complete_task(callback_query):
    task_id = callback_query.data.split("_")[1]
    
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT task, status FROM tasks WHERE id = ?", (task_id,)) as cursor:
            task = await cursor.fetchone()  # Используем fetchone() у курсора

        if task:
            task_name, current_status = task
            new_status = 1 if current_status == 0 else 0
            await db.execute("UPDATE tasks SET status = ? WHERE id = ?", (new_status, task_id))
            await db.commit()

    status_emoji = "✅" if new_status == 1 else "❌"
    task_button = InlineKeyboardButton(
        text=f"{task_name} {status_emoji}",
        callback_data=f"view_{task_id}"
    )
    complete_button = InlineKeyboardButton(
        text="Завершить" if new_status == 0 else "Восстановить",
        callback_data=f"complete_{task_id}"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[[task_button, complete_button]])

    await callback_query.message.edit_text(f"Ваши задания:", reply_markup=keyboard)
    await callback_query.answer()






# Регистрация хендлеров для callback
dp.callback_query.register(process_view_task, lambda c: c.data and c.data.startswith("view_"))
dp.callback_query.register(process_complete_task, lambda c: c.data and c.data.startswith("complete_"))


async def on_startup():
    await db_init()
    print("Database initialized")


async def main():
    await on_startup()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
