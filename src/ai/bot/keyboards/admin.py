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
    [InlineKeyboardButton(text="Магазин", url="t.me/elixirpeptidebot/test")],
])

admin_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Пользователи", callback_data='admin:users:search:start')]
])

search_users_choice = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="ФИО", callback_data='admin:users:search:full_name')],
    [InlineKeyboardButton(text="Телеграм ID", callback_data='admin:users:search:id'),
     [InlineKeyboardButton(text="Телеграм username", callback_data='admin:users:search:username'),]]
    [InlineKeyboardButton(text="Номер телефона", callback_data='admin:users:search:phone'),
     InlineKeyboardButton(text="Почта", callback_data='admin:users:search:email')]
])