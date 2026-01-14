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
    [InlineKeyboardButton(text='💸 Расходы Ассистента', callback_data='admin:spends')],
    [InlineKeyboardButton(text="👥 Пользователи", switch_inline_query_current_chat='search_user start')]
])

search_users_choice = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="ФИО", switch_inline_query_current_chat='search_user full_name ')],
    [InlineKeyboardButton(text="Телеграм ID", switch_inline_query_current_chat='search_user id '),
     InlineKeyboardButton(text="Телеграм username", switch_inline_query_current_chat='search_user username ')],
    [InlineKeyboardButton(text="Номер телефона", switch_inline_query_current_chat='search_user phone '),
     InlineKeyboardButton(text="Почта", switch_inline_query_current_chat='search_user email ')]
])