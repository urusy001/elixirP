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

    #TODO: add additional step to handle the approach of giveaway codes (all to 1 or 1 to 1)
    #todo: add minimal grade and review length steps
