from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.deep_linking import create_start_link

from config import OWNER_TG_IDS, LOGS_DIR
from src.giveaway.bot.keyboards import user_keyboards
from src.giveaway.bot.states import user_states
from src.giveaway.bot.texts import user_texts, get_giveaway_text
from src.helpers import extract_email, cypher_user_id, _notify_user
from src.webapp import get_session
from src.webapp.crud import (
    get_giveaways,
    get_giveaway,
    get_participant,
    update_participant,
    create_participant,
    count_refs_for_participant,
    get_participant_no_giveaway,
)
from src.webapp.models import Participant
from src.webapp.schemas import ParticipantUpdate, ParticipantCreate


user_message_filter = lambda message: (message.from_user and message.from_user.id not in OWNER_TG_IDS and message and message.chat.type == "private")
user_call_filter = lambda call: (call.data.startswith("user") and call.from_user.id not in OWNER_TG_IDS and call.message.chat.type == "private")

router = Router(name="user")
logger = logging.getLogger("Розыгрыши user")

logs_path = Path(LOGS_DIR)
logs_path.mkdir(parents=True, exist_ok=True)
log_file = logs_path / f"{logger.name}.txt"

logger.setLevel(logging.INFO)
if not any(isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", None) == str(log_file) for h in logger.handlers):
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            "%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(fh)


async def build_closed_text(giveaway, user_id: int) -> str:
    """
    Возвращает текст закрытого розыгрыша + код участия юзера (если есть).
    Если giveaway=None — просто дефолтный текст без кода.
    """
    if giveaway and giveaway.closed_message:
        text = giveaway.closed_message
    else:
        text = "Этот розыгрыш уже завершён."

    if giveaway:
        async with get_session() as session:
            participant = await get_participant(session, giveaway.id, user_id)
        if participant and participant.participation_code:
            text += f"\n\nВаш код участия: <code>{participant.participation_code}</code>"

    return text


async def check_completion(session, giveaway_id: int, tg_id: int, participant, message: Message) -> Participant:
    """Check if all requirements are done and assign participation code if yes."""
    logger.debug(
        "check_completion | giveaway_id=%s | tg_id=%s | is_completed=%s | has_code=%s",
        giveaway_id,
        tg_id,
        getattr(participant, "is_completed", None),
        getattr(participant, "participation_code", None),
    )

    giveaway = await get_giveaway(session, giveaway_id)
    if giveaway and giveaway.closed:
        logger.info("check_completion skipped for closed giveaway | giveaway_id=%s | tg_id=%s", giveaway_id, tg_id)
        text = await build_closed_text(giveaway, tg_id)
        await message.answer(text)
        return participant

    if participant and participant.is_completed and not getattr(participant, "participation_code", None):
        code = cypher_user_id(tg_id)
        update_data = ParticipantUpdate(participation_code=code)
        updated = await update_participant(session, giveaway_id, tg_id, update_data)
        logger.info("Assigned participation_code for user %s in giveaway %s | code=%s", tg_id, giveaway_id, code)
        await message.answer(f"🎉 Поздравляем! Вы выполнили все условия розыгрыша.\nВаш код участия: <code>{code}</code>")
        return updated

    return participant


@router.message(CommandStart(deep_link=True, deep_link_encoded=True), user_message_filter)
async def handle_ref_start(message: Message, command: CommandStart, state: FSMContext):
    logger.info("handle_ref_start | user_id=%s | args=%r", message.from_user.id, command.args)

    args = command.args or ""
    parts = args.split("_")

    if len(parts) != 2:
        logger.warning("Invalid referral args for user %s: %r", message.from_user.id, args)
        await message.answer("Ошибка реферальной ссылки, начато без реферала")
        return await handle_start(message, state)

    ref_id, giveaway_id = parts[0], int(parts[1])
    logger.debug("Parsed referral for user %s: ref_id=%s, giveaway_id=%s", message.from_user.id, ref_id, giveaway_id)

    async with get_session() as session:
        giveaway = await get_giveaway(session, giveaway_id)

    if not giveaway:
        logger.warning("Referral to non-existing giveaway | user_id=%s | giveaway_id=%s", message.from_user.id, giveaway_id)
        await message.answer("Этот розыгрыш не найден.")
        return await handle_start(message, state)

    if giveaway.closed:
        logger.info("Referral to closed giveaway | user_id=%s | giveaway_id=%s", message.from_user.id, giveaway_id)
        text = await build_closed_text(giveaway, message.from_user.id)
        await message.answer(text)
        return await handle_start(message, state)

    async with get_session() as session:
        participant = await get_participant_no_giveaway(session, message.from_user.id)

    if participant:
        logger.info("User %s already registered in giveaways DB", message.from_user.id)
        await message.answer("Данный аккаунт уже был зарегистрирован в базе розыгрышей, повторно записать его не получится.")
        return await handle_start(message, state)

    create_data = ParticipantCreate(tg_id=message.from_user.id, ref_id=ref_id, giveaway_id=giveaway_id)

    async with get_session() as session:
        participant = await create_participant(session, create_data)
        logger.info("Created participant via referral | user_id=%s | giveaway_id=%s | ref_id=%s", message.from_user.id, giveaway_id, ref_id)

    return await message.answer(
        f"💬 Подпишитесь на чат @{giveaway.channel_username}\nПосле подписки, пожалуйста, <b>воспользуйтесь кнопкой ниже ⬇️ для проверки</b>",
        reply_markup=user_keyboards.ChatSubscription(giveaway.id),
    )


@router.message(CommandStart(deep_link=False), user_message_filter)
async def handle_start(message: Message, state: FSMContext):
    logger.info("handle_start | user_id=%s", message.from_user.id)
    await state.clear()
    async with get_session() as session:
        giveaways = await get_giveaways(session)
    logger.debug("Loaded %d giveaways for main menu", len(giveaways))
    await message.answer(user_texts.main_menu.replace('*', message.from_user.full_name), reply_markup=user_keyboards.ViewGiveaways([giveaway for giveaway in giveaways if not giveaway.closed]))
    await message.delete()


@router.message(user_states.Requirements.email, lambda message: (message.from_user and message.from_user.id not in OWNER_TG_IDS and message.text and message.text.strip() and message.chat.type == "private"))
async def handle_email(message: Message, state: FSMContext):
    logger.info("handle_email | user_id=%s | raw_text=%r", message.from_user.id, message.text)

    email = extract_email(message.text.strip())
    if not email:
        logger.warning("Invalid email from user %s: %r", message.from_user.id, message.text)
        return await _notify_user(message, "❌ Введите корректный email", logger=logger)

    logger.debug("Extracted email for user %s: %s", message.from_user.id, email)
    state_data = await state.get_data()
    giveaway_id = state_data["giveaway_id"]
    logger.debug("handle_email | giveaway_id=%s", giveaway_id)

    async with get_session() as session:
        giveaway = await get_giveaway(session, giveaway_id)

    if not giveaway or giveaway.closed:
        logger.info("Email step for closed/non-existing giveaway | user_id=%s | giveaway_id=%s", message.from_user.id, giveaway_id)
        if giveaway:
            text = await build_closed_text(giveaway, message.from_user.id)
        else:
            text = "Этот розыгрыш уже завершён."
        await message.answer(text)
        await state.clear()
        return None

    async with get_session() as session:
        from src.giveaway.reviews import review_client
        result = await review_client.get_valid_review(
            email=email,
            since_dt=giveaway.start_date,
            min_grade=giveaway.minimal_review_grade,
            min_length=giveaway.minimal_review_length,
            session=session,
        )

    logger.info("Review check result for user %s | giveaway_id=%s | ok=%s", message.from_user.id, giveaway_id, result.get("ok", False))

    if result.get("ok", False):
        review = result["review"]
        review_id = review["id"]
        fullname = review.get("fullname", "")
        phone = (
            (review.get("phone") or "")
            .replace("-", "")
            .replace("(", "")
            .replace(")", "")
        )

        update_data = ParticipantUpdate(
            completed_review=True,
            review_id=review_id,
            review_email=email,
            review_phone=phone,
            review_fullname=fullname,
        )

        async with get_session() as session:
            participant = await update_participant(session, giveaway_id, message.from_user.id, update_data)
            logger.info("Updated participant with review for user %s | giveaway_id=%s | review_id=%s", message.from_user.id, giveaway_id, review_id)
            await check_completion(session, giveaway_id, message.from_user.id, participant, message)

        prefix = "✅ "
    else:
        prefix = "❌ "

    text = f"{prefix}{result.get('html_message', 'Ошибка в обработке запроса')}"
    return asyncio.create_task(_notify_user(message, text, logger=logger))


@router.message(lambda message: (message.from_user and message.from_user.id not in OWNER_TG_IDS and message.contact and message.chat.type == "private"))
async def handle_contact(message: Message):
    phone_number = message.contact.phone_number
    full_name = message.from_user.full_name

    logger.info("handle_contact | user_id=%s | full_name=%r | phone=%r", message.from_user.id, full_name, phone_number)
    await message.answer("Спасибо, с вами скоро свяжутся")
    for admin_id in OWNER_TG_IDS:
        await message.bot.send_message(admin_id, f"Номер тг {full_name}: {phone_number}")
        logger.debug("Sent contact of %s to admin %s", message.from_user.id, admin_id)


@router.message(user_states.Requirements.order_code, lambda message: (message.from_user and message.from_user.id not in OWNER_TG_IDS and message.text and message.text.strip().isdigit() and message.chat.type == "private"))
async def handle_order_code(message: Message, state: FSMContext):
    logger.info("handle_order_code | user_id=%s | raw_text=%r", message.from_user.id, message.text)
    order_code = int(message.text.strip())
    logger.debug("Parsed order_code for user %s: %s", message.from_user.id, order_code)
    state_data = await state.get_data()
    giveaway_id = state_data["giveaway_id"]

    async with get_session() as session1, get_session() as session2:
        giveaway_task = get_giveaway(session1, giveaway_id)
        participant_task = get_participant(session2, giveaway_id, message.from_user.id)
        giveaway, participant = await asyncio.gather(giveaway_task, participant_task)

    if not giveaway or giveaway.closed:
        logger.info("Order-code step for closed/non-existing giveaway | user_id=%s | giveaway_id=%s", message.from_user.id, giveaway_id)
        if giveaway:
            text = await build_closed_text(giveaway, message.from_user.id)
        else:
            text = "Этот розыгрыш уже завершён."
        await message.answer(text)
        await state.clear()
        return

    logger.debug("Loaded giveaway and participant for order check | user_id=%s | giveaway_id=%s", message.from_user.id, giveaway_id)

    async with get_session() as session:
        from src.amocrm.client import amocrm
        result = await amocrm.get_valid_deal(order_code, giveaway.start_date, session)

    logger.info("Deal check result for user %s | giveaway_id=%s | order_code=%s | ok=%s", message.from_user.id, giveaway_id, order_code, result.get("ok", False))

    if result.get("ok", False):
        update_data = ParticipantUpdate(completed_deal=True, deal_code=order_code)

        async with get_session() as session:
            participant = await update_participant(session, giveaway_id, message.from_user.id, update_data)
            participant = await check_completion(session, giveaway_id, message.from_user.id, participant, message)

        prefix = "✅ "
    else:
        prefix = "❌ "

    text = f"{prefix}{result.get('html_message', 'Ошибка в обработке запроса')}"
    asyncio.create_task(_notify_user(message, text, logger=logger))

    giveaway_text = get_giveaway_text(giveaway)
    await message.answer(giveaway_text, reply_markup=(user_keyboards.GiveawayMenu(giveaway_id, participant) if participant else user_keyboards.Participate(giveaway_id)))


@router.callback_query(user_call_filter)
async def handle_user_call(call: CallbackQuery, state: FSMContext, giveaway_bot):
    data = call.data.split(":")[1:]
    user_id = call.from_user.id
    logger.info("handle_user_call | user_id=%s | data=%r", user_id, data)

    if data[0] == "main_menu":
        await handle_start(call.message, state)

    elif data[0] == "view_giveaways" and data[1].isdigit():
        giveaway_id = int(data[1])
        logger.debug("User %s viewing giveaway %s", user_id, giveaway_id)

        async with get_session() as session1, get_session() as session2:
            giveaway_task = get_giveaway(session1, giveaway_id)
            participant_task = get_participant(session2, giveaway_id, user_id)
            participant, giveaway = await asyncio.gather(participant_task, giveaway_task)

        if not giveaway:
            return await call.message.edit_text("Этот розыгрыш не найден.")

        if giveaway.closed:
            text = await build_closed_text(giveaway, user_id)
            return await call.message.edit_text(text)

        giveaway_text = get_giveaway_text(giveaway)
        await call.message.edit_text(
            giveaway_text,
            reply_markup=(user_keyboards.GiveawayMenu(giveaway_id, participant) if participant else user_keyboards.Participate(giveaway_id)),
        )

    elif data[0] == "participate" and data[1].isdigit():
        giveaway_id = int(data[1])
        logger.info("User %s participates in giveaway %s", user_id, giveaway_id)

        async with get_session() as session:
            giveaway = await get_giveaway(session, giveaway_id)

        if not giveaway or giveaway.closed:
            logger.info("Participate attempt in closed/non-existing giveaway | user_id=%s | giveaway_id=%s", user_id, giveaway_id)
            text = await build_closed_text(giveaway, user_id) if giveaway else "Этот розыгрыш уже завершён."
            return await asyncio.create_task(_notify_user(call.message, text, 120, logger))

        async with get_session() as session1, get_session() as session2:
            create_data = ParticipantCreate(tg_id=user_id, giveaway_id=giveaway_id)
            participant_task = create_participant(session1, create_data)
            giveaway_task = get_giveaway(session2, giveaway_id)
            participant, giveaway = await asyncio.gather(participant_task, giveaway_task)

        giveaway_text = get_giveaway_text(giveaway)
        await call.message.edit_text(giveaway_text, reply_markup=(user_keyboards.GiveawayMenu(giveaway_id, participant) if participant else user_keyboards.Participate(giveaway_id)))

    elif data[0].startswith("check_") and data[1].isdigit():
        what = data[0][6:]
        giveaway_id = int(data[1])
        logger.info("User %s requested check_%s | giveaway_id=%s", user_id, what, giveaway_id)

        async with get_session() as session:
            giveaway = await get_giveaway(session, giveaway_id)

        if not giveaway or giveaway.closed:
            logger.info("Check_%s in closed/non-existing giveaway | user_id=%s | giveaway_id=%s", what, user_id, giveaway_id)
            text = await build_closed_text(giveaway, user_id) if giveaway else "Этот розыгрыш уже завершён."
            return await asyncio.create_task(_notify_user(call.message, text, 120, logger))

        if what == "subscription":
            result = await giveaway_bot.is_user_subscribed(user_id, giveaway.channel_username)
            logger.info("Subscription check | user_id=%s | channel=@%s | result=%s", user_id, giveaway.channel_username, result)

            if result:
                update_data = ParticipantUpdate(completed_subscription=True)
                async with get_session() as session:
                    participant = await update_participant(session, giveaway_id, user_id, update_data)
                    await check_completion(session, giveaway_id, user_id, participant, call.message)

                text = f"✅ Ваша подписка на @{giveaway.channel_username} <b>успешно подтверждена!</b>"
            else:
                text = f"❌ Ваша подписка на @{giveaway.channel_username} <b>не подтверждена</b>"

        elif what == "refs":
            async with get_session() as session:
                refs = await count_refs_for_participant(session, giveaway_id, user_id, completed_subscription=True)
            logger.info("Refs check | user_id=%s | giveaway_id=%s | refs=%s | required=%s", user_id, giveaway_id, refs, giveaway.minimal_referral_amount)

            if refs >= giveaway.minimal_referral_amount:
                update_data = ParticipantUpdate(completed_refs=True)

                async with get_session() as session:
                    participant = await update_participant(session, giveaway_id, user_id, update_data)
                    await check_completion(session, giveaway_id, user_id, participant, call.message)

                text = f"✅ {refs} ваших друзей <b>успешно выполнили условие подписки</b> на @{giveaway.channel_username}"
            else:
                start_link = await create_start_link(call.bot, f"{user_id}_{giveaway_id}", True)
                text = (
                    f"❌ Вы привели <b>{refs}/{giveaway.minimal_referral_amount}</b> "
                    f"друзей по ссылке: <b>{start_link}</b>\n\n"
                    "<i>Приведённые друзья должны <b>пройти проверку подписки</b> "
                    "для участия в розыгрыше.</i>"
                )

        else:
            logger.debug("Switching to input mode %s for user %s | giveaway_id=%s", what, user_id, giveaway_id)
            if what in ["deal", "review"]:
                await state.update_data(giveaway_id=giveaway_id)
                await state.set_state(user_states.Requirements.order_code if what == "deal" else user_states.Requirements.email)
                await call.message.edit_text(user_texts.order_code if what == "deal" else user_texts.email, reply_markup=user_keyboards.BackToGiveaway(giveaway_id))
            return None

        asyncio.create_task(_notify_user(call.message, text, 120, logger))

    return None