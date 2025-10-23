from aiogram.fsm.state import State, StatesGroup

class OrderAndReview(StatesGroup):
    order_code = State()
    email = State()

