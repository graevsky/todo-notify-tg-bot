import aiosqlite
import asyncio
import os
from dotenv import load_dotenv
from datetime import datetime
import pytz


load_dotenv()

DB_FILE = os.getenv("DB_FILENAME")
time_format = "%H:%M"
db_clear_period = int(os.getenv("DB_CLEAR_PERIOD"))


async def db_init():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            """CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY,
            user_id INTEGER, task TEXT, description TEXT,
              status INTEGER DEFAULT 0)"""
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS
              user_settings (user_id INTEGER PRIMARY KEY, 
            description_optional INTEGER DEFAULT 0,
            reminder_optional INTEGER DEFAULT 0, reminder_time TEXT)
              """
        )
        await db.execute(
            """CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            notification_name TEXT,
            notification_date TEXT,
            notification_time TEXT,
            is_active INTEGER DEFAULT 1)"""
        )
        await db.commit()


# Settings
async def get_user_settings(user_id):
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute(
            """SELECT description_optional, reminder_optional,
            reminder_time FROM user_settings WHERE user_id = ?""",
            (user_id,),
        )
        settings = await cursor.fetchone()

        if settings is None:
            await db.execute(
                """INSERT INTO user_settings (user_id,
                description_optional,reminder_optional,
                reminder_time) VALUES (?, 0, 0, NULL)""",
                (user_id,),
            )
            await db.commit()
            settings = (0, 0, None)
        return {
            "description_optional": settings[0],
            "reminder_optional": settings[1],
            "reminder_time": settings[2],
        }


async def toggle_description_optional(user_id):
    async with aiosqlite.connect(DB_FILE) as db:
        user_settings = await get_user_settings(user_id)
        current_setting = user_settings["description_optional"]
        new_setting = 1 if current_setting == 0 else 0
        await db.execute(
            """UPDATE user_settings SET
            description_optional = ? WHERE user_id = ?""",
            (new_setting, user_id),
        )
        await db.commit()
        return new_setting


async def toggle_reminder_optional(user_id):
    async with aiosqlite.connect(DB_FILE) as db:
        settings = await get_user_settings(user_id)
        current_setting = settings["reminder_optional"]

        new_setting = 1 if current_setting == 0 else 0

        await db.execute(
            "UPDATE user_settings SET reminder_optional = ? WHERE user_id = ?",
            (new_setting, user_id),
        )
        await db.commit()
        return new_setting


async def update_reminder_time(user_id, reminder_time):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "UPDATE user_settings SET reminder_time = ? WHERE user_id = ?",
            (reminder_time, user_id),
        )
        await db.commit()


async def reminder_scheduler(bot):
    while True:
        now = datetime.now(pytz.timezone("Europe/Moscow")).strftime("%H:%M")

        async with aiosqlite.connect(DB_FILE) as db:
            cursor = await db.execute(
                """SELECT user_id FROM user_settings WHERE
                reminder_optional = 1 AND reminder_time = ?""",
                (now,),
            )
            users = await cursor.fetchall()

        if users:
            for user in users:
                user_id = user[0]
                tasks = await get_tasks(user_id)
                if tasks:
                    await bot.send_message(user_id, "Your tasks for today:")
                    for task in tasks:
                        task_text = f"{task[1]} {'✅' if task[3] == 1 else '❌'}"
                        await bot.send_message(user_id, task_text)

        await asyncio.sleep(60)


async def notification_scheduler(bot):
    while True:
        now = datetime.now(pytz.timezone("Europe/Moscow"))

        async with aiosqlite.connect(DB_FILE) as db:
            cursor = await db.execute(
                """SELECT id, user_id, notification_name FROM notifications 
                WHERE notification_date = ? AND
                notification_time = ? AND is_active = 1""",
                (now.strftime("%d.%m.%Y"), now.strftime("%H:%M")),
            )
            notifications = await cursor.fetchall()

        if notifications:
            for notification in notifications:
                notification_id, user_id, notification_name = notification

                await bot.send_message(user_id, f"Reminder: {notification_name}")

                async with aiosqlite.connect(DB_FILE) as db:
                    await db.execute(
                        "UPDATE notifications SET is_active = 0 WHERE id = ?",
                        (notification_id,),
                    )
                    await db.commit()

        await asyncio.sleep(60)


async def get_tasks(user_id):
    async with aiosqlite.connect(DB_FILE) as db:
        tasks = await db.execute_fetchall(
            """SELECT id, task, description,
            status FROM tasks where user_id = ? AND status = 0""",
            (user_id,),
        )
        return tasks


async def get_single_task(task_id):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute(
            "SELECT task, description, status FROM tasks WHERE id = ?", (task_id,)
        ) as cursor:
            task = await cursor.fetchone()
        return task


async def update_task_status(task_id, new_status):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "UPDATE tasks SET status = ? WHERE id = ?", (new_status, task_id)
        )
        await db.commit()


async def set_task_name(task_id, task_name):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("UPDATE tasks SET task = ? WHERE id = ?", (task_name, task_id))
        await db.commit()


async def get_task_description(task_id):
    async with aiosqlite.connect(DB_FILE) as db:
        task = await db.execute_fetchall(
            "SELECT description FROM tasks WHERE id = ?", (task_id,)
        )
        return task


async def insert_task(user_id, task, description):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "INSERT INTO tasks (user_id, task, description) VALUES (?, ?, ?)",
            (user_id, task, description),
        )
        await db.commit()


async def get_notifications(user_id):
    async with aiosqlite.connect(DB_FILE) as db:
        notifications = await db.execute_fetchall(
            """SELECT id, notification_name, notification_date,
            notification_time FROM notifications 
            WHERE user_id = ? AND is_active = 1""",
            (user_id,),
        )
        return notifications


async def get_single_notification(notification_id):
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute(
            """SELECT notification_name, notification_date, notification_time
            FROM notifications WHERE id = ?""",
            (notification_id,),
        )
        return await cursor.fetchone()


async def insert_notification(
    user_id, notification_name, notification_date, notification_time
):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            """INSERT INTO notifications
            (user_id, notification_name, notification_date, notification_time)
            VALUES (?, ?, ?, ?)""",
            (user_id, notification_name, notification_date, notification_time),
        )
        await db.commit()


async def update_notification(notification_id, notification_date, notification_time):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            """UPDATE notifications SET notification_date = ?,
            notification_time = ? WHERE id = ?""",
            (notification_date, notification_time, notification_id),
        )
        await db.commit()


async def disable_notification(notification_id):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "UPDATE notifications SET is_active = 0 WHERE id = ?",
            (notification_id,),
        )
        await db.commit()


async def task_deletion_scheduler():
    while True:
        await clear_tasks()
        await clear_notifications()
        await asyncio.sleep(db_clear_period)


async def clear_tasks():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("DELETE FROM tasks WHERE status = 1")
        await db.commit()


async def clear_notifications():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("DELETE FROM notifications WHERE is_active = 0")
        await db.commit()
