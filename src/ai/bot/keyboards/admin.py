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
    [InlineKeyboardButton(text="👥 Пользователи", callback_data='admin:users:search')]
])

search_users_choice = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Телеграм ФИО", switch_inline_query_current_chat='search_user full_name ')],
    [InlineKeyboardButton(text="Телеграм ID", switch_inline_query_current_chat='search_user tg_id '),
     InlineKeyboardButton(text="Телеграм username", switch_inline_query_current_chat='search_user username ')],
    [InlineKeyboardButton(text="Номер телефона", switch_inline_query_current_chat='search_user phone '),
     InlineKeyboardButton(text="Почта", switch_inline_query_current_chat='search_user email ')]
])

back_button = InlineKeyboardButton(text="🔙 Главное меню", callback_data='admin:main_menu')
back = InlineKeyboardMarkup(inline_keyboard=[[back_button]])

backk_button = InlineKeyboardButton(text="🔙 Главное меню", callback_data='admin:main_menuu')
backk = InlineKeyboardMarkup(inline_keyboard=[[backk_button]])

def fast_unblock(user_id: int): return InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔓 Разблокировать", callback_data=f'admin:users:{user_id}:unblock')],
    [back_button]
])

def view_user_menu(user_id: int, carts_len: int, blocked: bool):
    if not blocked: block_button = InlineKeyboardButton(text="🔐 Заблокировать", callback_data=f'admin:users:{user_id}:block')
    else: block_button = InlineKeyboardButton(text="🔓 Разблокировать", callback_data=f'admin:users:{user_id}:unblock')
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🛍️ Заказы ({carts_len})", callback_data=f"admin:users:{user_id}:orders"),
         InlineKeyboardButton(text="💬 История", callback_data=f"admin:users:{user_id}:history")],
        [block_button], [back_button]
    ])