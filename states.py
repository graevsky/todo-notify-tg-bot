from aiogram.fsm.state import StatesGroup, State


class TaskStates(StatesGroup):
    waiting_for_task_name = State()
    waiting_for_task_description = State()
    waiting_for_task_edit = State()


class ReminderStates(StatesGroup):
    waiting_for_reminder_time = State()


class NotificationStates(StatesGroup):
    waiting_for_notification_name = State()
    waiting_for_notification_date = State()
    waiting_for_notification_time = State()
    waiting_for_notification_edit_date = State()
    waiting_for_notification_edit_time = State()
