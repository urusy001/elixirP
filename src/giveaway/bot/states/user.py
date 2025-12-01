from aiogram.fsm.state import State, StatesGroup


class Requirements(StatesGroup):
    order_code = State()
    email = State()
