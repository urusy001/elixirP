from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

from src.webapp.models import Giveaway

main_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='🗓️ Просмотреть текущие розыгрыши', callback_data='admin:view_giveaways:start')],
    [InlineKeyboardButton(text='➕ Создать новый розыгрыш', callback_data='admin:create_giveaway:start')],
])

no_giveaways = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='➕ Создать первый розыгрыш', callback_data='admin:create_giveaway:start')],
])

skip = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='Пропустить', callback_data='admin:create_giveaway:skip')],
])

winner_keyboard = ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True, keyboard=[
    [KeyboardButton(request_contact=True, text='📲 Поделиться')]
])


class ViewGiveaways(InlineKeyboardMarkup):
    def __init__(self, giveaways: list[Giveaway]):
        buttons = [InlineKeyboardButton(text=giveaway.name, callback_data=f'admin:view_giveaways:{giveaway.id}') for
                   giveaway in giveaways]
        keyboard = [buttons[i: i + 2] for i in range(0, len(buttons), 2)]
        keyboard.append([InlineKeyboardButton(text='🔙 Главное меню', callback_data='admin:main_menu')])
        super().__init__(inline_keyboard=keyboard)


class GiveawayMenu(InlineKeyboardMarkup):
    def __init__(self, giveaway_id, closed: bool = False):
        keyboard = [
            [InlineKeyboardButton(text='👥 Посмотреть участников', callback_data=f'admin:view_participants:{giveaway_id}'),
             InlineKeyboardButton(text='🔒 Закрыть розыгрыш', callback_data=f'admin:close_giveaway:{giveaway_id}') if not closed else
             InlineKeyboardButton(text='🍾 Открыть розыгрыш', callback_data=f'admin:open_giveaway:{giveaway_id}')],
            [InlineKeyboardButton(text='🗑️ Удалить розыгрыш', callback_data=f'admin:delete_giveaway:{giveaway_id}')], #TODO: Add a button Изменить розыгрыш which leads to a menu of chosing what to change
            [InlineKeyboardButton(text='🔙 Главное меню', callback_data='admin:main_menu')],
        ]
        super().__init__(inline_keyboard=keyboard)


#TODO: Add child buttons for each attribute of a Изменить розыгрыш