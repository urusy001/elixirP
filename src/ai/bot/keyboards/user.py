from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

phone = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True, keyboard=[
    [KeyboardButton(text='Подтвердить', request_contact=True)]
])
