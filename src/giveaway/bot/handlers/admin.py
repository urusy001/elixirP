from datetime import datetime, timedelta

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from config import ADMIN_TG_IDS, MOSCOW_TZ
from src.giveaway.bot.keyboards import admin_keyboards
from src.giveaway.bot.keyboards.admin import GiveawayMenu
from src.giveaway.bot.states import admin_states
from src.giveaway.bot.texts import admin_texts, get_giveaway_text
from src.webapp import get_session
from src.webapp.crud import create_giveaway, get_giveaways, get_giveaway
from src.webapp.schemas import GiveawayCreate

router = Router(name="user")

@router.message(CommandStart(), lambda message: message.from_user and message.from_user.id in ADMIN_TG_IDS)
async def handle_admin_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(admin_texts.main_menu, reply_markup=admin_keyboards.main_menu)
    await message.delete()

@router.message(admin_states.CreateGiveaway.name, lambda message: message.from_user and message.from_user.id in ADMIN_TG_IDS and message.text and message.text.strip())
async def handle_giveaway_name(message: Message, state: FSMContext):
    giveaway_name = message.text.strip()
    await state.update_data(name=giveaway_name)
    await state.set_state(admin_states.CreateGiveaway.prize)
    await message.answer(admin_texts.CreateGiveaway.prize)

@router.message(admin_states.CreateGiveaway.prize, lambda message: message.from_user and message.from_user.id in ADMIN_TG_IDS and message.text and message.text.strip())
async def handle_giveaway_prize(message: Message, state: FSMContext):
    prize_rows = message.text.strip().split('\n')
    giveaway_prize = {row.split('. ')[0]: row.split('. ')[1] for row in prize_rows}
    await state.update_data(prize=giveaway_prize)
    await state.set_state(admin_states.CreateGiveaway.description)
    await message.answer(admin_texts.CreateGiveaway.description)

@router.message(admin_states.CreateGiveaway.description, lambda message: message.from_user and message.from_user.id in ADMIN_TG_IDS and message.text and message.text.strip())
async def handle_giveaway_description(message: Message, state: FSMContext):
    giveaway_description = message.text.strip()
    await state.update_data(description=giveaway_description)
    await state.set_state(admin_states.CreateGiveaway.channel_username)
    await message.answer(admin_texts.CreateGiveaway.channel_username)

@router.message(admin_states.CreateGiveaway.channel_username, lambda message: message.from_user and message.from_user.id in ADMIN_TG_IDS and message.text and message.text.strip())
async def handle_giveaway_channel_username(message: Message, state: FSMContext, giveaway_bot):
    giveaway_channel_username = message.text.strip().removeprefix('@')
    if not await giveaway_bot.is_channel_admin(giveaway_channel_username): await message.answer(admin_texts.CreateGiveaway.bot_not_admin.replace('*', giveaway_channel_username))
    else:
        await state.update_data(channel_username=giveaway_channel_username)
        await state.set_state(admin_states.CreateGiveaway.referral_amount)
        await message.answer(admin_texts.CreateGiveaway.referral_amount, reply_markup=admin_keyboards.skip)

@router.message(admin_states.CreateGiveaway.referral_amount, lambda message: message.from_user and message.from_user.id in ADMIN_TG_IDS and message.text and message.text.strip().isdigit())
async def handle_giveaway_referral_amount(message: Message, state: FSMContext):
    giveaway_referral_amount = int(message.text.strip())
    await state.update_data(referral_amount=giveaway_referral_amount)
    await state.set_state(admin_states.CreateGiveaway.end_date)
    await message.answer(admin_texts.CreateGiveaway.end_date)

@router.message(admin_states.CreateGiveaway.end_date, lambda message: message.from_user and message.from_user.id in ADMIN_TG_IDS and message.text and message.text.strip().isdigit())
async def handle_end_date(message: Message, state: FSMContext):
    days = int(message.text.strip())
    end_datetime = datetime.now(MOSCOW_TZ) + timedelta(days=days)
    await state.update_data(end_date=end_datetime)
    data = GiveawayCreate(**(await state.get_data()))
    async with get_session() as session: giveaway = await create_giveaway(session, data)
    await message.answer(get_giveaway_text(giveaway), reply_markup=GiveawayMenu(giveaway.id))


@router.callback_query(lambda call: call.data.startswith("admin") and call.from_user and call.from_user.id in ADMIN_TG_IDS)
async def handle_admin_call(call: CallbackQuery, state: FSMContext):
    data = call.data.split(':')[1:]
    current_state = await state.get_state()
    state_data = await state.get_data()
    if data[0] == "main_menu":
        await handle_admin_start(call.message, state)

    elif data[0] == "create_giveaway":
        if data[1] == "start":
            await state.set_state(admin_states.CreateGiveaway.name)
            await call.message.edit_text(admin_texts.CreateGiveaway.name)

        elif data[1] == "skip":
            if current_state == admin_states.CreateGiveaway.referral_amount:
                await state.update_data(referral_amount=None)
                await state.set_state(admin_states.CreateGiveaway.end_date)
                await call.message.edit_text(admin_texts.CreateGiveaway.end_date, reply_markup=admin_keyboards.skip)

            elif current_state == admin_states.CreateGiveaway.end_date:
                await state.update_data(end_date=None)
                data = GiveawayCreate(**(await state.get_data()))
                async with get_session() as session: giveaway = await create_giveaway(session, data)
                await call.message.edit_text(get_giveaway_text(giveaway), reply_markup=GiveawayMenu(giveaway.id))

    elif data[0] == "view_giveaways":
        if data[1] == "start":
            async with get_session() as session: giveaways = await get_giveaways(session)
            if giveaways: await call.message.edit_text(admin_texts.view_giveaway, reply_markup=admin_keyboards.ViewGiveaways(giveaways))
            else: await call.message.edit_text(admin_texts.no_giveaways, reply_markup=admin_keyboards.no_giveaways)

        elif data[1].isdigit():
            giveaway_id = int(data[1])
            async with get_session() as session: giveaway = await get_giveaway(session, giveaway_id)
            await call.message.edit_text(get_giveaway_text(giveaway), reply_markup=GiveawayMenu(giveaway_id))
