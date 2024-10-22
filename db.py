import aiosqlite
import asyncio

DB_FILE = "tasks.db"
time_format = "%H:%M"

async def db_init():
    async with aiosqlite.connect("DB_FILE") as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, user_id INTEGER UNIQUE)"
        )
        await db.execute(
            "CREATE TABLE tasks (id INTEGER PRIMARY KEY, user_id INTEGER, task TEXT, description TEXT, status INTEGER DEFAULT 0)"
        )
        await db.commit()
        

# TODO: tasks deletion daily or after finish?