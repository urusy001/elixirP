from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart
from aiogram.utils.deep_linking import create_start_link

from config import ADMIN_TG_IDS
from src.giveaway.bot.texts import user_texts, get_giveaway_text
from src.giveaway.bot.keyboards import user_keyboards
from src.webapp import get_session
from src.webapp.crud import get_giveaways, get_giveaway, get_participant

router = Router(name="user")

@router.message(CommandStart(deep_link=True, deep_link_encoded=True), lambda message: message.from_user and message.from_user.id not in ADMIN_TG_IDS)
async def handle_ref_start(message: Message, command: CommandStart, state: FSMContext):
    args = command.args or ""
    parts = args.split("_")

    if len(parts) != 2:
        await message.answer('Ошибка реферальной ссылки, начато без реферала')
        await handle_start(message, state)

    ref_id, giveaway_id = parts[0], parts[1]

    await message.answer(
        f"✅ Referral start detected!\nRef ID: {ref_id}\nGiveaway ID: {giveaway_id}"
    )

    await state.update_data(ref_id=ref_id, giveaway_id=giveaway_id)

@router.message(CommandStart(deep_link=False), lambda message: message.from_user and message.from_user.id not in ADMIN_TG_IDS)
async def handle_start(message: Message, state: FSMContext):
    await state.clear()
    async with get_session() as session: giveaways = await get_giveaways(session)
    await message.answer(user_texts.main_menu, reply_markup=user_keyboards.ViewGiveaways(giveaways))


@router.callback_query(lambda call: call.data.startswith("user") and call.from_user.id not in ADMIN_TG_IDS)
async def handle_user_call(call: CallbackQuery, state: FSMContext):
    data = call.data.split(":")[1:]
    state_data = await state.get_data()
    if data[0] == "view_giveaways":
        if data[1].isdigit():
            giveaway_id = int(data[1])
            async with get_session() as session:
                giveaway = await get_giveaway(session, giveaway_id)
                participant = await get_participant(session, giveaway_id, call.from_user.id)

            giveaway_text = get_giveaway_text(giveaway)
            await call.message.edit_text(giveaway_text, reply_markup=user_keyboards.GiveawayMenu(giveaway_id, participant))

    elif data[0] == "":
