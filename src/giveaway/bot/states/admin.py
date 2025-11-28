from aiogram.fsm.state import State, StatesGroup


class CreateGiveaway(StatesGroup):
    name = State()
    prize = State()
    description = State()
    channel_username = State()
    referral_amount = State()
    end_date = State()
    closed_text = State()
    delete = State()
