import asyncio

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.deep_linking import create_start_link

from config import ADMIN_TG_IDS
from src.giveaway.bot.keyboards import user_keyboards
from src.giveaway.bot.states import user_states
from src.giveaway.bot.texts import user_texts, get_giveaway_text
from src.helpers import extract_email, cypher_user_id
from src.webapp import get_session
from src.webapp.crud import (
    get_giveaways,
    get_giveaway,
    get_participant,
    update_participant,
    create_participant,
    count_refs_for_participant,
)
from src.webapp.models import Participant
from src.webapp.schemas import ParticipantUpdate, ParticipantCreate

user_message_filter = lambda \
    message: message.from_user and message.from_user.id not in ADMIN_TG_IDS and message and message.chat.type == "private"
user_call_filter = lambda call: call.data.startswith(
    "user") and call.from_user.id not in ADMIN_TG_IDS and call.message.chat.type == "private"

router = Router(name="user")


async def _notify_user(message: Message, text: str, timer: float | None = None):
    x = await message.answer(text)
    if timer:
        await asyncio.sleep(timer)
        await x.delete()


async def check_completion(session, giveaway_id: int, tg_id: int, participant, message: Message) -> Participant:
    """Check if all requirements are done and assign participation code if yes."""
    if participant and participant.is_completed and not getattr(participant, "participation_code", None):
        code = cypher_user_id(tg_id)
        update_data = ParticipantUpdate(participation_code=code)
        updated = await update_participant(session, giveaway_id, tg_id, update_data)
        await message.answer(
            f"🎉 Поздравляем! Вы выполнили все условия розыгрыша.\n"
            f"Ваш код участия: <code>{code}</code>"
        )
        return updated
    return participant


@router.message(
    CommandStart(deep_link=True, deep_link_encoded=True),
    user_message_filter,
)
async def handle_ref_start(message: Message, command: CommandStart, state: FSMContext):
    args = command.args or ""
    parts = args.split("_")

    if len(parts) != 2:
        await message.answer("Ошибка реферальной ссылки, начато без реферала")
        return await handle_start(message, state)

    ref_id, giveaway_id = parts[0], parts[1]
    async with get_session() as session:
        create_data = ParticipantCreate(
            tg_id=message.from_user.id,
            ref_id=ref_id,
            giveaway_id=giveaway_id,
        )
        await create_participant(session, create_data)

    return await handle_start(message, state)


@router.message(
    CommandStart(deep_link=False),
    user_message_filter,
)
async def handle_start(message: Message, state: FSMContext):
    await state.clear()
    async with get_session() as session:
        giveaways = await get_giveaways(session)
    await message.answer(
        user_texts.main_menu,
        reply_markup=user_keyboards.ViewGiveaways(giveaways),
    )
    await message.delete()


@router.message(
    user_states.Requirements.email,
    lambda message: message.from_user and message.from_user.id not in ADMIN_TG_IDS and message.text and message.text.strip() and message.chat.type == "private",
)
async def handle_email(message: Message, state: FSMContext):
    email = extract_email(message.text.strip())
    if not email:
        return await _notify_user(message, "❌ Введите корректный email")

    state_data = await state.get_data()
    giveaway_id = state_data["giveaway_id"]

    async with get_session() as session:
        giveaway = await get_giveaway(session, giveaway_id)

    async with get_session() as session:
        from src.giveaway.reviews import review_client
        result = await review_client.get_valid_review(
            email=email,
            since_dt=giveaway.start_date,
            min_grade=giveaway.minimal_review_grade,
            min_length=giveaway.minimal_review_length,
            session=session,
        )

    if result.get("ok", False):
        review = result["review"]
        review_id = review["id"]
        fullname = review.get("fullname", "")
        phone = (review.get("phone") or "").replace("-", "").replace("(", "").replace(")", "")
        update_data = ParticipantUpdate(
            completed_review=True,
            review_id=review_id,
            review_email=email,
            review_phone=phone,
            review_fullname=fullname,
        )
        async with get_session() as session:
            participant = await update_participant(session, giveaway_id, message.from_user.id, update_data)
            await check_completion(session, giveaway_id, message.from_user.id, participant, message)
        prefix = "✅ "
    else:
        prefix = "❌ "

    text = f"{prefix}{result.get('html_message', 'Ошибка в обработке запроса')}"
    return asyncio.create_task(_notify_user(message, text))


@router.message(
    lambda message: message.from_user and message.from_user.id not in ADMIN_TG_IDS and message.contact and message.chat.type == "private")
async def handle_contact(message: Message):
    phone_number = message.contact.phone_number
    full_name = message.from_user.full_name
    await message.answer('Спасибо, с вами скоро свяжутся')
    [await message.bot.send_message(i, f'Номер тг {full_name}: {phone_number}') for i in ADMIN_TG_IDS]


@router.message(
    user_states.Requirements.order_code,
    lambda message: message.from_user and message.from_user.id not in ADMIN_TG_IDS and message.text and message.text.strip().isdigit() and message.chat.type == "private",
)
async def handle_order_code(message: Message, state: FSMContext):
    order_code = int(message.text.strip())
    state_data = await state.get_data()
    giveaway_id = state_data["giveaway_id"]

    async with get_session() as session1, get_session() as session2:
        giveaway_task = get_giveaway(session1, giveaway_id)
        participant_task = get_participant(session2, giveaway_id, message.from_user.id)
        giveaway, participant = await asyncio.gather(giveaway_task, participant_task)

    async with get_session() as session:
        from src.amocrm.client import amocrm
        result = await amocrm.get_valid_deal(order_code, giveaway.start_date, session)

    if result.get("ok", False):
        update_data = ParticipantUpdate(completed_deal=True, deal_code=order_code)
        async with get_session() as session:
            participant = await update_participant(session, giveaway_id, message.from_user.id, update_data)
            participant = await check_completion(session, giveaway_id, message.from_user.id, participant, message)
        prefix = "✅ "
    else:
        prefix = "❌ "

    text = f"{prefix}{result.get('html_message', 'Ошибка в обработке запроса')}"
    asyncio.create_task(_notify_user(message, text))

    giveaway_text = get_giveaway_text(giveaway)
    await message.answer(
        giveaway_text,
        reply_markup=user_keyboards.GiveawayMenu(giveaway_id, participant)
        if participant
        else user_keyboards.Participate(giveaway_id),
    )


@router.callback_query(
    user_call_filter
)
async def handle_user_call(call: CallbackQuery, state: FSMContext, giveaway_bot):
    data = call.data.split(":")[1:]
    user_id = call.from_user.id
    if data[0] == "main_menu":
        await handle_start(call.message, state)
    elif data[0] == "view_giveaways" and data[1].isdigit():
        giveaway_id = int(data[1])
        async with get_session() as session1, get_session() as session2:
            giveaway_task = get_giveaway(session1, giveaway_id)
            participant_task = get_participant(session2, giveaway_id, user_id)
            participant, giveaway = await asyncio.gather(participant_task, giveaway_task)

        giveaway_text = get_giveaway_text(giveaway)
        await call.message.edit_text(
            giveaway_text,
            reply_markup=user_keyboards.GiveawayMenu(giveaway_id, participant)
            if participant
            else user_keyboards.Participate(giveaway_id),
        )

    elif data[0] == "participate" and data[1].isdigit():
        giveaway_id = int(data[1])
        async with get_session() as session1, get_session() as session2:
            create_data = ParticipantCreate(tg_id=user_id, giveaway_id=giveaway_id)
            participant_task = create_participant(session1, create_data)
            giveaway_task = get_giveaway(session2, giveaway_id)
            participant, giveaway = await asyncio.gather(participant_task, giveaway_task)

        giveaway_text = get_giveaway_text(giveaway)
        await call.message.edit_text(
            giveaway_text,
            reply_markup=user_keyboards.GiveawayMenu(giveaway_id, participant)
            if participant
            else user_keyboards.Participate(giveaway_id),
        )

    elif data[0].startswith("check_") and data[1].isdigit():
        what = data[0][6:]
        giveaway_id = int(data[1])
        async with get_session() as session:
            giveaway = await get_giveaway(session, giveaway_id)

        if what == "subscription":
            result = await giveaway_bot.is_user_subscribed(user_id, giveaway.channel_username)
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
            if refs >= giveaway.minimal_referral_amount:
                update_data = ParticipantUpdate(completed_refs=True)
                async with get_session() as session:
                    participant = await update_participant(session, giveaway_id, user_id, update_data)
                    await check_completion(session, giveaway_id, user_id, participant, call.message)
                text = (
                    f"✅ {refs} ваших друзей <b>успешно выполнили условие подписки</b> "
                    f"на @{giveaway.channel_username}"
                )
            else:
                start_link = await create_start_link(call.bot, f"{user_id}_{giveaway_id}", True)
                text = (
                    f"❌ Вы привели <b>{refs}/{giveaway.minimal_referral_amount}</b> друзей по ссылке: "
                    f"<code>{start_link}</code>\n\n"
                    f"<i>Приведённые друзья должны <b>пройти проверку подписки</b> "
                    f"для участия в розыгрыше.</i>"
                )

        else:
            if what in ["deal", "review"]:
                await state.update_data(giveaway_id=giveaway_id)
                await state.set_state(
                    user_states.Requirements.order_code
                    if what == "deal"
                    else user_states.Requirements.email
                )
                await call.message.edit_text(
                    user_texts.order_code if what == "deal" else user_texts.email,
                    reply_markup=user_keyboards.BackToGiveaway(giveaway_id),
                )
            return

        asyncio.create_task(_notify_user(call.message, text, 120))
