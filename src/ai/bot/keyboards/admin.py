from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

main_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='💸 Расходы Ассистента', callback_data='admin:spends')],
])

spend_times = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='1️⃣ Этот день', callback_data='admin:spends:1'),
     InlineKeyboardButton(text='Неделя 7️⃣', callback_data='admin:spends:7')],
    [InlineKeyboardButton(text='🗓 Месяц️', callback_data='admin:spends:30'),
     InlineKeyboardButton(text='Все время ♾️', callback_data='admin:spends:0')],
])

open_test = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Магазин", web_app=WebAppInfo(url="https://elixirpeptides.devsivanschostakov.org"))]
])
