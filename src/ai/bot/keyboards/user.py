from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

phone = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True, keyboard=[
    [KeyboardButton(text='Подтвердить', request_contact=True)]
])

open_app = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Открыть магазин ", web_app=WebAppInfo(url="https://elixirpeptides.devsivanschostakov.org"))],
    [InlineKeyboardButton(text="Оферта", callback_data="user:offer"), InlineKeyboardButton(text="Данные ИП", callback_data="user:about")]
])

main_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='🤖 ИИ Эксперт', callback_data="user:ai:start"),
     InlineKeyboardButton(text='✖️ Калькуляторы ➗', callback_data="user:calculators:start")],
    [InlineKeyboardButton(text="Открыть магазин ", web_app=WebAppInfo(url="https://elixirpeptides.devsivanschostakov.org"))],
    [InlineKeyboardButton(text='💬 Отзывы', callback_data="user:reviews:start"),
     InlineKeyboardButton(text="Оферта", callback_data="user:offer"),
     InlineKeyboardButton(text="Данные ИП", callback_data="user:about")]
])

pick_ai = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='✨Премиум 4.1', callback_data="user:ai:premium"),
     InlineKeyboardButton(text='Бесплатная 4.1-mini', callback_data="user:ai:free")]
])