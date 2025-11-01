from aiogram.fsm.state import State, StatesGroup


class Registration(StatesGroup):
    phone = State()
