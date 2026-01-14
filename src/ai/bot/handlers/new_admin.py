from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from src.ai.bot.texts import admin_texts
from src.ai.bot.handlers import new_admin_router
from src.ai.bot.keyboards import admin_keyboards

@new_admin_router.message(CommandStart())
async def handle_start(message: Message):
    await message.answer(admin_texts.greeting, reply_markup=admin_keyboards.admin_menu)

@new_admin_router.callback_query()
async def handle_callback_query(call: CallbackQuery, state: FSMContext):
    data = call.data.removeprefix("admin:").split(':')
    print(data)
    state_data = await state.get_data()
    if data[0] == "users":
        if data[1] == "search":
            if data[2] == "start":
                await call.message.edit_text(admin_texts.search_users_choice, reply_markup=admin_keyboards.search_users_choice)
