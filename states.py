from aiogram.fsm.state import StatesGroup, State


class TaskStates(StatesGroup):
    waiting_for_task_name = State()
    waiting_for_task_description = State()
    waiting_for_task_edit = State()


class ReminderStates(StatesGroup):
    waiting_for_reminder_time = State()
