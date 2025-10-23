from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from src.webapp.models import Giveaway, Participant


class ViewGiveaways(InlineKeyboardMarkup):
    def __init__(self, giveaways: list[Giveaway]):
        buttons = [InlineKeyboardButton(text=giveaway.name, callback_data=f'user:view_giveaways:{giveaway.id}') for giveaway in giveaways]
        keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
        keyboard.append([InlineKeyboardButton(text='📝 Главное меню', callback_data='user:main_menu')])
        super().__init__(inline_keyboard=keyboard)

class GiveawayMenu(InlineKeyboardMarkup):
    def __init__(self, giveaway_id: int, participant: Participant):
        buttons = []
        if not participant.completed_deal: buttons.append(InlineKeyboardButton(text='🛍️ Покупка', callback_data=f'user:check_deal:{giveaway_id}'))
        if not participant.completed_review: buttons.append(InlineKeyboardButton(text='💬 Отзыв', callback_data=f'user:check_review:{giveaway_id}'))
        if not participant.completed_subscription: buttons.append(InlineKeyboardButton(text='➕ Подписка', callback_data=f'user:check_subscription:{giveaway_id}'))
        if not participant.completed_refs: buttons.append(InlineKeyboardButton(text='👥 Друзья', callback_data=f'user:check_refs:{giveaway_id}'))
        keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
        keyboard.append([InlineKeyboardButton(text='📝 Главное меню', callback_data='user:main_menu')])
        super().__init__(inline_keyboard=keyboard)

