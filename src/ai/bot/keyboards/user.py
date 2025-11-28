from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

phone = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True, keyboard=[
    [KeyboardButton(text='Подтвердить', request_contact=True)]
])

open_app = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Открыть  магазин ", web_app=WebAppInfo(url="https://elixirpeptides.devsivanschostakov.org"))]
])
