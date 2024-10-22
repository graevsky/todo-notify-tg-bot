import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

import aiosqlite
import asyncio

from db import DB_FILE, db_init
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

@dp.message(Command("start"))
async def start_command(message: Message):
    await message.answer("Test.")



async def on_startup():
    await db_init()
    print("Database initialized")


async def main():
    await on_startup()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
