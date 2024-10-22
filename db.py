import aiosqlite
import asyncio

DB_FILE = "tasks.db"
time_format = "%H:%M"

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


# TODO: tasks deletion daily or after finish?