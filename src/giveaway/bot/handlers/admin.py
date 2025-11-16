import asyncio
import os
import random
from datetime import datetime, timedelta

import pandas as pd
from aiogram import Router
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, FSInputFile, ReplyKeyboardMarkup, KeyboardButton

from config import ADMIN_TG_IDS, MOSCOW_TZ, GIVEAWAYS_DIR
from src.giveaway.bot.keyboards import admin_keyboards
from src.giveaway.bot.keyboards.admin import GiveawayMenu
from src.giveaway.bot.states import admin_states
from src.giveaway.bot.texts import admin_texts, get_giveaway_text
from src.webapp import get_session
from src.webapp.crud import create_giveaway, get_giveaways, get_giveaway, get_participants, delete_giveaway
from src.webapp.schemas import GiveawayCreate

router = Router(name="user")
router.callback_query.filter(~StateFilter(admin_states.CreateGiveaway.delete))


@router.callback_query(admin_states.CreateGiveaway.delete,
                       lambda call: call.from_user and call.from_user.id in ADMIN_TG_IDS and call.message.chat.type == "private")
async def block_callbacks_during_delete(call: CallbackQuery):
    await call.answer("Сначала подтвердите/отмените удаление.", show_alert=True)


@router.message(admin_states.CreateGiveaway.delete,
                lambda message: message.from_user and message.from_user.id in ADMIN_TG_IDS and message.chat.type == "private")
async def handle_delete_giveaway(message: Message, state: FSMContext):
    if not message.text or message.text.strip().lower() not in ["да", "нет"]:
        x = await message.answer('Следуй инструкциям')
        await asyncio.sleep(5)
        await x.delete()

    else:
        action = message.text.strip().lower()
        state_data = await state.get_data()
        giveaway_id = state_data["giveaway_id"]
        to_delete = state_data["to_delete"]
        async with get_session() as session:
            await delete_giveaway(session, giveaway_id)
        await message.bot.edit_message_text(
            '✅ Розыгрыш успешно <b>удален</b>\n\n<i>Записи о всех его участниках тоже удалены</i>' if action == 'да' else '❌ Удаление <b>прервано</b>',
            chat_id=message.chat.id, message_id=to_delete)
        await handle_admin_start(message, state)

        async def proceed():
            await asyncio.sleep(5)
            await message.bot.delete_message(message.chat.id, to_delete)

        asyncio.create_task(proceed())


@router.message(CommandStart(),
                lambda message: message.from_user and message.from_user.id in ADMIN_TG_IDS and message.chat.type == "private")
async def handle_admin_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(admin_texts.main_menu, reply_markup=admin_keyboards.main_menu)
    await message.delete()


@router.message(Command('winner'),
                lambda message: message.from_user and message.from_user.id in ADMIN_TG_IDS and message.chat.type == "private")
async def handle_winner(message: Message):
    args = message.text.removeprefix('/winner ').split(' ')
    if len(args) < 3 or not (args[0].isdigit() and args[1].isdigit()):
        return await message.answer('Ошибка команды — /winner giveaway_id place winner_code')
    else:
        giveaway_id = int(args[0])
        place = args[1]
        winner_code = args[2]
        async with get_session() as session1, get_session() as session2:
            participants = await get_participants(session1, giveaway_id)
            giveaway = await get_giveaway(session2, giveaway_id)

        prize = giveaway.prize.get(place, None)
        if not prize: return await message.answer(f'Ошибка команды — за {place} <b>место приз не найден</b>')
        if winner_code == 'random':
            participants = [participant for participant in participants if
                            participant.is_completed and participant.participation_code]
            winner = random.choice(participants)
        else:
            winner = next((p for p in participants if p.participation_code == winner_code), None)
        if winner:
            winner_text = f'<b>🏆 Выбран победитель для розыгрыша {giveaway.name}🥳</b>\nПриз за {place} место — {prize}\n\n<i>Ему будет отправлены уведомление и запрос оставить свой номер тг</i>'
            await message.answer(winner_text)
            return asyncio.create_task(message.bot.send_message(winner.tg_id, winner_text.replace(
                'Ему будет отправлены уведомление и запрос оставить свой номер тг',
                'Пожалуйста, оставьте свой номер телефона кнопкой ниже'), reply_markup=ReplyKeyboardMarkup(keyboard=[
                [KeyboardButton(text='📲 Поделиться', request_contact=True)]
            ], resize_keyboard=True, one_time_keyboard=True)))

        else:
            return await message.answer('Ошибка команды — <b>победитель с кодом не найден</b>')


@router.message(admin_states.CreateGiveaway.name,
                lambda message: message.from_user and message.from_user.id in ADMIN_TG_IDS and message.chat.type == "private" and message.text and message.text.strip())
async def handle_giveaway_name(message: Message, state: FSMContext):
    giveaway_name = message.text.strip()
    await state.update_data(name=giveaway_name)
    await state.set_state(admin_states.CreateGiveaway.prize)
    await message.answer(admin_texts.CreateGiveaway.prize)


@router.message(admin_states.CreateGiveaway.prize,
                lambda message: message.from_user and message.from_user.id in ADMIN_TG_IDS and message.chat.type == "private" and message.text and message.text.strip())
async def handle_giveaway_prize(message: Message, state: FSMContext):
    prize_rows = message.text.strip().split('\n')
    giveaway_prize = {row.split('. ')[0]: row.split('. ')[1] for row in prize_rows}
    await state.update_data(prize=giveaway_prize)
    await state.set_state(admin_states.CreateGiveaway.description)
    await message.answer(admin_texts.CreateGiveaway.description)


@router.message(admin_states.CreateGiveaway.description,
                lambda message: message.from_user and message.from_user.id in ADMIN_TG_IDS and message.chat.type == "private" and message.text and message.text.strip())
async def handle_giveaway_description(message: Message, state: FSMContext):
    giveaway_description = message.text.strip()
    await state.update_data(description=giveaway_description)
    await state.set_state(admin_states.CreateGiveaway.channel_username)
    await message.answer(admin_texts.CreateGiveaway.channel_username)


@router.message(admin_states.CreateGiveaway.channel_username,
                lambda message: message.from_user and message.from_user.id in ADMIN_TG_IDS and message.chat.type == "private" and message.text and message.text.strip())
async def handle_giveaway_channel_username(message: Message, state: FSMContext, giveaway_bot):
    giveaway_channel_username = message.text.strip().removeprefix('@')
    if not await giveaway_bot.is_channel_admin(giveaway_channel_username):
        await message.answer(admin_texts.CreateGiveaway.bot_not_admin.replace('*', giveaway_channel_username))
    else:
        await state.update_data(channel_username=giveaway_channel_username)
        await state.set_state(admin_states.CreateGiveaway.referral_amount)
        await message.answer(admin_texts.CreateGiveaway.referral_amount, reply_markup=admin_keyboards.skip)


@router.message(admin_states.CreateGiveaway.referral_amount,
                lambda message: message.from_user and message.from_user.id in ADMIN_TG_IDS and message.chat.type == "private" and message.text and message.text.strip().isdigit())
async def handle_giveaway_referral_amount(message: Message, state: FSMContext):
    giveaway_referral_amount = int(message.text.strip())
    await state.update_data(minimal_referral_amount=giveaway_referral_amount)
    await state.set_state(admin_states.CreateGiveaway.end_date)
    await message.answer(admin_texts.CreateGiveaway.end_date, keyboard=admin_keyboards.skip)


@router.message(admin_states.CreateGiveaway.end_date,
                lambda message: message.from_user and message.from_user.id in ADMIN_TG_IDS and message.chat.type == "private" and message.text and message.text.strip().isdigit())
async def handle_end_date(message: Message, state: FSMContext):
    days = int(message.text.strip())
    end_datetime = datetime.now(MOSCOW_TZ) + timedelta(days=days)
    await state.update_data(end_date=end_datetime)
    data = GiveawayCreate(**(await state.get_data()))
    async with get_session() as session: giveaway = await create_giveaway(session, data)
    await message.answer(get_giveaway_text(giveaway), reply_markup=GiveawayMenu(giveaway.id))


@router.callback_query(lambda call: call.data.startswith(
    "admin") and call.from_user and call.from_user.id in ADMIN_TG_IDS and call.message.chat.type == "private")
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
                await state.update_data(minimal_referral_amount=None)
                await state.set_state(admin_states.CreateGiveaway.end_date)
                await call.message.edit_text(admin_texts.CreateGiveaway.end_date, reply_markup=admin_keyboards.skip)

            elif current_state == admin_states.CreateGiveaway.end_date:
                await state.update_data(end_date=None)
                data = GiveawayCreate(**(await state.get_data()))
                async with get_session() as session:
                    giveaway = await create_giveaway(session, data)
                await call.message.edit_text(get_giveaway_text(giveaway), reply_markup=GiveawayMenu(giveaway.id))

    elif data[0] == "view_giveaways":
        if data[1] == "start":
            async with get_session() as session:
                giveaways = await get_giveaways(session)
            if giveaways:
                await call.message.edit_text(admin_texts.view_giveaway,
                                             reply_markup=admin_keyboards.ViewGiveaways(giveaways))
            else:
                await call.message.edit_text(admin_texts.no_giveaways, reply_markup=admin_keyboards.no_giveaways)

        elif data[1].isdigit():
            giveaway_id = int(data[1])
            async with get_session() as session:
                giveaway = await get_giveaway(session, giveaway_id)
            await call.message.edit_text(get_giveaway_text(giveaway), reply_markup=GiveawayMenu(giveaway_id))

    elif data[0] == "view_participants":
        if data[1].isdigit():
            giveaway_id = int(data[1])
            async with get_session() as session1, get_session() as session2:
                participants_task = get_participants(session1, giveaway_id)
                giveaway_task = get_giveaway(session2, giveaway_id)
                participants, giveaway = await asyncio.gather(participants_task, giveaway_task)

            participants_info = [{
                'Полное имя': participant.review_fullname,
                'Номер телефона': participant.review_phone,
                'Эл. почта': participant.review_email,
                'Телеграм ID': participant.tg_id,
                'Номер заказа': participant.deal_code,
                'ID Отзыва': participant.review_id,
                'Код участника': participant.participation_code
            } for participant in participants if participant.participation_code]
            df = pd.DataFrame(participants_info)

            filename = os.path.join(GIVEAWAYS_DIR, f"{giveaway_id}_{datetime.now():%Y%m%d_%H%M%S}.xlsx")
            df.to_excel(filename, index=False)

            await call.message.answer_document(
                FSInputFile(filename),
                caption=f"📊 Завершённые участники розыгрыша <b>{giveaway.name}</b>\nВсего: {len(df)}\n\n<b>Команда: <code>/winner {giveaway_id} место код</code></b>"
            )

            try:
                os.remove(filename)
            except OSError:
                pass

    elif data[0] == "delete_giveaway":
        if data[1].isdigit():
            giveaway_id = int(data[1])
            await state.set_state(admin_states.CreateGiveaway.delete)
            to_delete = (await call.message.answer(
                'Вы уверены что хотите <b>удалить розыгрыш?</b>\nВведите <code>да</code> / <code>нет</code>\n\n<i>Вы не сможете перейти к другим действиям пока не подтвердите/отмените удаление вводом</i>')).message_id
            await state.update_data(giveaway_id=giveaway_id, to_delete=to_delete)
