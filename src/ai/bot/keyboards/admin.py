from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

main_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='💸 Расходы Ассистента', callback_data='admin:spends')],
])

spend_times = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='1️⃣ Этот день', callback_data='admin:spends:null'),
     InlineKeyboardButton(text='Неделя 7️⃣', callback_data='admin:spends:7')],
    [InlineKeyboardButton(text='🗓 Месяц️', callback_data='admin:spends:30'),
     InlineKeyboardButton(text='Все время ♾️', callback_data='admin:spends:0')],
])