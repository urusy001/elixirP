import asyncio
import os
import random
from datetime import datetime, timedelta
from pathlib import Path
import logging

import pandas as pd
from aiogram import Router
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, FSInputFile, ReplyKeyboardMarkup, KeyboardButton

from config import OWNER_TG_IDS, MOSCOW_TZ, GIVEAWAYS_DIR, LOGS_DIR
from src.giveaway.bot.keyboards import admin_keyboards
from src.giveaway.bot.keyboards.admin import GiveawayMenu
from src.giveaway.bot.states import admin_states
from src.giveaway.bot.texts import admin_texts, get_giveaway_text
from src.webapp import get_session
from src.webapp.crud import create_giveaway, get_giveaways, get_giveaway, get_participants, delete_giveaway, update_giveaway
from src.webapp.schemas import GiveawayCreate, GiveawayUpdate

router = Router(name="admin")
router.callback_query.filter(~StateFilter(admin_states.CreateGiveaway.delete))
logger = logging.getLogger("Розыгрыши admin")
logs_path = Path(LOGS_DIR)
logs_path.mkdir(parents=True, exist_ok=True)
log_file = logs_path / f"{logger.name}.txt"

if not any(isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", None) == str(log_file)for h in logger.handlers):
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s","%Y-%m-%d %H:%M:%S"))
    logger.addHandler(fh)

logger.setLevel(logging.INFO)


@router.callback_query(admin_states.CreateGiveaway.delete, lambda call: call.from_user and call.from_user.id in OWNER_TG_IDS and call.message.chat.type == "private")
async def block_callbacks_during_delete(call: CallbackQuery):
    logger.info("block_callbacks_during_delete | admin_id=%s | data=%r", call.from_user.id, call.data)
    await call.answer("Сначала подтвердите/отмените удаление.", show_alert=True)


@router.message(admin_states.CreateGiveaway.delete, lambda message: message.from_user and message.from_user.id in OWNER_TG_IDS and message.chat.type == "private")
async def handle_delete_giveaway(message: Message, state: FSMContext):
    logger.info("handle_delete_giveaway | admin_id=%s | text=%r", message.from_user.id, message.text)
    if not message.text or message.text.strip().lower() not in ["да", "нет"]:
        x = await message.answer('Следуй инструкциям')
        await asyncio.sleep(5)
        await x.delete()
        logger.debug("handle_delete_giveaway | invalid input, reminder deleted")

    else:
        action = message.text.strip().lower()
        state_data = await state.get_data()
        giveaway_id = state_data["giveaway_id"]
        to_delete = state_data["to_delete"]

        if action == "да":
            async with get_session() as session: await delete_giveaway(session, giveaway_id)
            logger.info("Deleted giveaway | admin_id=%s | giveaway_id=%s", message.from_user.id, giveaway_id)
            await message.bot.edit_message_text('✅ Розыгрыш успешно <b>удален</b>\n\n<i>Записи о всех его участниках тоже удалены</i>', chat_id=message.chat.id, message_id=to_delete)

        else:
            logger.info("Deletion cancelled | admin_id=%s | giveaway_id=%s", message.from_user.id, giveaway_id)
            await message.bot.edit_message_text('❌ Удаление <b>прервано</b>', chat_id=message.chat.id, message_id=to_delete)

        await handle_admin_start(message, state)
        async def proceed():
            await asyncio.sleep(5)
            await message.bot.delete_message(message.chat.id, to_delete)
            logger.debug("Deleted confirmation message %s after delay | admin_id=%s", to_delete, message.from_user.id)

        asyncio.create_task(proceed())


@router.message(CommandStart(), lambda message: message.from_user and message.from_user.id in OWNER_TG_IDS and message.chat.type == "private")
async def handle_admin_start(message: Message, state: FSMContext):
    logger.info("handle_admin_start | admin_id=%s", message.from_user.id)
    await state.clear()
    await message.answer(admin_texts.main_menu, reply_markup=admin_keyboards.main_menu)
    await message.delete()


@router.message(Command('winner'), lambda message: message.from_user and message.from_user.id in OWNER_TG_IDS and message.chat.type == "private")
async def handle_winner(message: Message):
    logger.info("handle_winner | admin_id=%s | raw_text=%r", message.from_user.id, message.text)

    args = message.text.removeprefix('/winner ').split(' ')
    if len(args) < 3 or not (args[0].isdigit() and args[1].isdigit()):
        logger.warning("handle_winner | invalid args | admin_id=%s | args=%r", message.from_user.id, args)
        return await message.answer('Ошибка команды — /winner giveaway_id place winner_code')

    else:
        giveaway_id = int(args[0])
        place = args[1]
        winner_code = args[2]
        async with get_session() as session1, get_session() as session2:
            participants = await get_participants(session1, giveaway_id)
            giveaway = await get_giveaway(session2, giveaway_id)

        prize = giveaway.prize.get(place, None)
        if not prize:
            logger.warning("handle_winner | prize not found | admin_id=%s | giveaway_id=%s | place=%s", message.from_user.id, giveaway_id, place)
            return await message.answer(f'Ошибка команды — за {place} <b>место приз не найден</b>')

        if winner_code == 'random':
            participants = [participant for participant in participants if participant.is_completed and participant.participation_code]
            if not participants:
                logger.warning("handle_winner | no eligible participants for random | giveaway_id=%s",giveaway_id)
                return await message.answer("Нет завершённых участников для выбора победителя.")

            winner = random.choice(participants)
            logger.info("handle_winner | random winner chosen | giveaway_id=%s | tg_id=%s | place=%s", giveaway_id, winner.tg_id, place)

        else:
            winner = next((p for p in participants if p.participation_code == winner_code), None)
            logger.info("handle_winner | search by code | giveaway_id=%s | place=%s | code=%s | found=%s", giveaway_id, place, winner_code, bool(winner))

        if winner:
            winner_text = (
                f'<b>🏆 Выбран победитель для розыгрыша {giveaway.name}🥳</b>\n'
                f'Приз за {place} место — {prize}\n\n'
                f'<i>Ему будет отправлены уведомление и запрос оставить свой номер тг</i>'
            )
            await message.answer(winner_text)
            logger.info("handle_winner | notifying winner | tg_id=%s | giveaway_id=%s | place=%s", winner.tg_id, giveaway_id, place)
            return asyncio.create_task(
                message.bot.send_message(
                    winner.tg_id,
                    winner_text.replace(
                        'Ему будет отправлены уведомление и запрос оставить свой номер тг',
                        'Пожалуйста, оставьте свой номер телефона кнопкой ниже',
                    ),
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard=[[KeyboardButton(text='📲 Поделиться', request_contact=True)]],
                        resize_keyboard=True,
                        one_time_keyboard=True,
                    ),
                )
            )

        else:
            logger.warning("handle_winner | winner not found by code | giveaway_id=%s | place=%s | code=%s", giveaway_id, place, winner_code, )
            return await message.answer('Ошибка команды — <b>победитель с кодом не найден</b>')


@router.message(admin_states.CreateGiveaway.name, lambda message: message.from_user and message.from_user.id in OWNER_TG_IDS and message.chat.type == "private" and message.text and message.text.strip())
async def handle_giveaway_name(message: Message, state: FSMContext):
    giveaway_name = message.text.strip()
    logger.info("handle_giveaway_name | admin_id=%s | name=%r", message.from_user.id, giveaway_name)
    await state.update_data(name=giveaway_name)
    await state.set_state(admin_states.CreateGiveaway.prize)
    await message.answer(admin_texts.CreateGiveaway.prize)


@router.message(admin_states.CreateGiveaway.prize, lambda message: message.from_user and message.from_user.id in OWNER_TG_IDS and message.chat.type == "private" and message.text and message.text.strip())
async def handle_giveaway_prize(message: Message, state: FSMContext):
    prize_rows = message.text.strip().split('\n')
    giveaway_prize = {row.split('. ')[0]: row.split('. ')[1] for row in prize_rows}
    logger.info(
        "handle_giveaway_prize | admin_id=%s | prizes=%r",
        message.from_user.id,
        giveaway_prize,
    )
    await state.update_data(prize=giveaway_prize)
    await state.set_state(admin_states.CreateGiveaway.description)
    await message.answer(admin_texts.CreateGiveaway.description)


@router.message(admin_states.CreateGiveaway.description, lambda message: message.from_user and message.from_user.id in OWNER_TG_IDS and message.chat.type == "private" and message.text and message.text.strip())
async def handle_giveaway_description(message: Message, state: FSMContext):
    giveaway_description = message.text.strip()
    logger.info("handle_giveaway_description | admin_id=%s | len=%s", message.from_user.id, len(giveaway_description))
    await state.update_data(description=giveaway_description)
    await state.set_state(admin_states.CreateGiveaway.channel_username)
    await message.answer(admin_texts.CreateGiveaway.channel_username)


@router.message(admin_states.CreateGiveaway.channel_username, lambda message: message.from_user and message.from_user.id in OWNER_TG_IDS and message.chat.type == "private" and message.text and message.text.strip())
async def handle_giveaway_channel_username(message: Message, state: FSMContext, giveaway_bot):
    giveaway_channel_username = message.text.strip().removeprefix('@')
    logger.info("handle_giveaway_channel_username | admin_id=%s | channel=@%s", message.from_user.id, giveaway_channel_username)
    if not await giveaway_bot.is_channel_admin(giveaway_channel_username):
        logger.warning("Bot is not admin in channel @%s | admin_id=%s", giveaway_channel_username, message.from_user.id)
        await message.answer(admin_texts.CreateGiveaway.bot_not_admin.replace('*', giveaway_channel_username))
    else:
        await state.update_data(channel_username=giveaway_channel_username)
        await state.set_state(admin_states.CreateGiveaway.referral_amount)
        await message.answer(admin_texts.CreateGiveaway.referral_amount, reply_markup=admin_keyboards.skip)


@router.message(admin_states.CreateGiveaway.referral_amount, lambda message: (message.from_user and message.from_user.id in OWNER_TG_IDS and message.chat.type == "private" and message.text and message.text.strip().isdigit()))
async def handle_giveaway_referral_amount(message: Message, state: FSMContext):
    giveaway_referral_amount = int(message.text.strip())
    logger.info("handle_giveaway_referral_amount | admin_id=%s | amount=%s", message.from_user.id, giveaway_referral_amount)
    await state.update_data(minimal_referral_amount=giveaway_referral_amount)
    await state.set_state(admin_states.CreateGiveaway.end_date)
    await message.answer(admin_texts.CreateGiveaway.end_date, reply_markup=admin_keyboards.skip)


@router.message(admin_states.CreateGiveaway.end_date, lambda message: (message.from_user and message.from_user.id in OWNER_TG_IDS and message.chat.type == "private" and message.text and message.text.strip().isdigit()))
async def handle_end_date(message: Message, state: FSMContext):
    days = int(message.text.strip())
    end_datetime = datetime.now(MOSCOW_TZ) + timedelta(days=days)
    logger.info("handle_end_date | admin_id=%s | days=%s | end_datetime=%s", message.from_user.id, days, end_datetime)
    await state.update_data(end_date=end_datetime)
    await state.set_state(admin_states.CreateGiveaway.closed_text)
    await message.answer(
        "Введите текст, который будет показываться пользователям, "
        "если розыгрыш закрыт или завершён.\n\n"
        "Например: <i>Розыгрыш завершён, следите за новыми акциями в чате ❤️</i>",
    )


@router.message(admin_states.CreateGiveaway.closed_text, lambda message: (message.from_user and message.from_user.id in OWNER_TG_IDS and message.chat.type == "private" and message.text and message.text.strip()))
async def handle_closed_text(message: Message, state: FSMContext):
    closed_message = message.text.strip()
    logger.info("handle_closed_text | admin_id=%s | len=%s", message.from_user.id, len(closed_message))
    await state.update_data(closed_message=closed_message)

    data = GiveawayCreate(**(await state.get_data()))
    async with get_session() as session: giveaway = await create_giveaway(session, data)

    logger.info("Created giveaway | admin_id=%s | giveaway_id=%s | name=%r", message.from_user.id, giveaway.id, giveaway.name)
    await state.clear()
    await message.answer(get_giveaway_text(giveaway), reply_markup=GiveawayMenu(giveaway.id))


@router.callback_query(lambda call: call.data.startswith("admin") and call.from_user and call.from_user.id in OWNER_TG_IDS and call.message.chat.type == "private")
async def handle_admin_call(call: CallbackQuery, state: FSMContext):
    data = call.data.split(':')[1:]
    current_state = await state.get_state()
    state_data = await state.get_data()
    admin_id = call.from_user.id

    logger.info("handle_admin_call | admin_id=%s | data=%r | state=%r", admin_id, data, current_state)

    if data[0] == "main_menu": await handle_admin_start(call.message, state)

    elif data[0] == "create_giveaway":
        if data[1] == "start":
            logger.info("Admin %s starts create_giveaway", admin_id)
            await state.set_state(admin_states.CreateGiveaway.name)
            await call.message.edit_text(admin_texts.CreateGiveaway.name)

        elif data[1] == "skip":
            if current_state == admin_states.CreateGiveaway.referral_amount:
                logger.info("Admin %s skips referral_amount", admin_id)
                await state.update_data(minimal_referral_amount=None)
                await state.set_state(admin_states.CreateGiveaway.end_date)
                await call.message.edit_text(
                    admin_texts.CreateGiveaway.end_date,
                    reply_markup=admin_keyboards.skip,
                )

            elif current_state == admin_states.CreateGiveaway.end_date:
                logger.info("Admin %s skips end_date", admin_id)
                await state.update_data(end_date=None)
                data_obj = GiveawayCreate(**(await state.get_data()))
                async with get_session() as session: giveaway = await create_giveaway(session, data_obj)
                logger.info("Created giveaway via skip | admin_id=%s | giveaway_id=%s", admin_id, giveaway.id)
                await call.message.edit_text(
                    get_giveaway_text(giveaway),
                    reply_markup=GiveawayMenu(giveaway.id),
                )

    elif data[0] == "view_giveaways":
        if data[1] == "start":
            logger.info("Admin %s opens giveaways list", admin_id)
            async with get_session() as session: giveaways = await get_giveaways(session)
            if giveaways:
                await call.message.edit_text(
                    admin_texts.view_giveaway,
                    reply_markup=admin_keyboards.ViewGiveaways(giveaways),
                )
            else:
                await call.message.edit_text(
                    admin_texts.no_giveaways,
                    reply_markup=admin_keyboards.no_giveaways,
                )

        elif data[1].isdigit():
            giveaway_id = int(data[1])
            logger.info("Admin %s views giveaway %s", admin_id, giveaway_id)
            async with get_session() as session: giveaway = await get_giveaway(session, giveaway_id)
            await call.message.edit_text(
                get_giveaway_text(giveaway),
                reply_markup=GiveawayMenu(giveaway_id),
            )

    elif data[0] == "view_participants":
        if data[1].isdigit():
            giveaway_id = int(data[1])
            logger.info("Admin %s views participants for giveaway %s", admin_id, giveaway_id)
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

            logger.info("Exported participants for giveaway %s to %s | count=%s", giveaway_id, filename, len(df))

            await call.message.answer_document(
                FSInputFile(filename),
                caption=(
                    f"📊 Завершённые участники розыгрыша <b>{giveaway.name}</b>\n"
                    f"Всего: {len(df)}\n\n"
                    f"<b>Команда: <code>/winner {giveaway_id} место код</code></b>"
                )
            )

            try:
                os.remove(filename)
                logger.debug("Temp file %s removed", filename)
            except OSError as e: logger.warning("Failed to remove temp file %s: %s", filename, e)

    elif data[0] == "delete_giveaway":
        if data[1].isdigit():
            giveaway_id = int(data[1])
            logger.info("Admin %s initiates delete_giveaway %s", admin_id, giveaway_id)
            await state.set_state(admin_states.CreateGiveaway.delete)
            to_delete = (await call.message.answer(
                'Вы уверены что хотите <b>удалить розыгрыш?</b>\n'
                'Введите <code>да</code> / <code>нет</code>\n\n'
                '<i>Вы не сможете перейти к другим действиям пока не подтвердите/отмените удаление вводом</i>'
            )).message_id
            await state.update_data(giveaway_id=giveaway_id, to_delete=to_delete)

    elif data[0] == "close_giveaway":
        if data[1].isdigit():
            giveaway_id = int(data[1])
            logger.info("Admin %s initiates close_giveaway %s", admin_id, giveaway_id)
            update_data = GiveawayUpdate(closed=True)
            async with get_session() as session: giveaway = await update_giveaway(session, giveaway_id, update_data)
            await call.message.edit_text(
                f"🔒 <b>Розыгрыш успешно закрыт</b>\n{call.message.text}",
                reply_markup=GiveawayMenu(giveaway_id, True),
            )

    elif data[0] == "open_giveaway":
        if data[1].isdigit():
            giveaway_id = int(data[1])
            logger.info("Admin %s initiates open_giveaway %s", admin_id, giveaway_id)
            update_data = GiveawayUpdate(closed=False)
            async with get_session() as session: giveaway = await update_giveaway(session, giveaway_id, update_data)
            await call.message.edit_text(
                f"🍾 <b>Розыгрыш успешно открыт</b>\n{call.message.text}",
                reply_markup=GiveawayMenu(giveaway_id, False),
            )
