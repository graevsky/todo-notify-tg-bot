import aiosqlite
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

DB_FILE = os.getenv("DB_FILENAME")
time_format = "%H:%M"
db_clear_period = int(os.getenv("DB_CLEAR_PERIOD"))

async def db_init():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, user_id INTEGER UNIQUE)"
        )
        await db.execute(
            "CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, user_id INTEGER, task TEXT, description TEXT, status INTEGER DEFAULT 0)"
        )
        await db.commit()
        
async def get_tasks(user_id):
    async with aiosqlite.connect(DB_FILE) as db:
        tasks = await db.execute_fetchall(
            "SELECT id, task, description, status FROM tasks where user_id = ?", (user_id,)
        )
        return tasks

async def task_deletion_scheduler():
    await clear_tasks()
    await asyncio.sleep(db_clear_period)

async def clear_tasks():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("DELETE FROM tasks WHERE status == 1")
        await db.commit()
