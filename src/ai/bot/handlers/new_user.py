import asyncio
from datetime import datetime
from aiogram import Router
from aiogram.enums import ChatType
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, Message, CallbackQuery, ReplyKeyboardRemove

from config import OWNER_TG_IDS, MOSCOW_TZ, DATA_DIR, PROFESSOR_ASSISTANT_ID, NEW_ASSISTANT_ID, BOT_KEYWORDS
from src.ai.calc import generate_drug_graphs, plot_filled_scale
from src.helpers import CHAT_NOT_BANNED_FILTER, _notify_user, with_typing, _fmt
from src.webapp import get_session
from src.webapp.crud import write_usage, increment_tokens, get_user, update_user
from src.webapp.schemas import UserUpdate
from src.ai.bot.texts import user_texts
from src.ai.bot.keyboards import user_keyboards
from src.ai.bot.states import user_states

async def _(x: Message):
    await asyncio.sleep(15)
    await x.delete()

new_user_router = Router(name="shop_user")
new_user_router.message.filter(lambda message: message.from_user.id not in OWNER_TG_IDS and message.chat.type == ChatType.PRIVATE)
new_user_router.callback_query.filter(lambda call: call.data.startswith("user") and call.from_user.id not in OWNER_TG_IDS and call.message.chat.type == ChatType.PRIVATE)

@new_user_router.message(Command('shop'))
async def app(message: Message): await message.answer(user_texts.offer, reply_markup=user_keyboards.open_app)

@new_user_router.message(Command('about'))
async def about(message: Message):
    x = await message.answer(user_texts.about)
    asyncio.create_task(_(x))

@new_user_router.message(Command('offer'))
async def offer(message: Message):
    x = await message.answer_document(FSInputFile(DATA_DIR / 'offer.pdf'), caption=user_texts.offer)
    asyncio.create_task(_(x))

@new_user_router.message(Command('clicks'))
async def clicks(message: Message, state: FSMContext):
    await message.answer(user_texts.cartridge_volume, reply_markup=user_keyboards.cartridge_volume)
    await state.set_state(user_states.CalculateClicks.cartridge_volume)
    await message.delete()

@new_user_router.message(Command('divisions'))
async def divisions(message: Message, state: FSMContext):
    await message.answer(user_texts.vial_amount, reply_markup=user_keyboards.back)
    await state.set_state(user_states.CalculateDivisions.vial_amount)
    await message.delete()

@new_user_router.message(Command('graph'))
async def graph(message: Message):
    await message.answer(user_texts.choose_peptide, reply_markup=user_keyboards.peptides_keyboard)
    await message.delete()

@new_user_router.message(CommandStart())
async def handle_user_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    result = await CHAT_NOT_BANNED_FILTER(user_id)
    if not result: return await message.answer(user_texts.banned_in_channel)
    async with get_session() as session: user = await get_user(session, 'tg_id', user_id)
    if not user:
        await state.set_state(user_states.Registration.phone)
        return await message.answer(user_texts.verify_phone.replace('*', message.from_user.full_name), reply_markup=user_keyboards.phone)

    if user.blocked_until and user.blocked_until.replace(tzinfo=MOSCOW_TZ) > datetime.now(MOSCOW_TZ): return await message.answer(user_texts.banned_until.replace("Блокировка до 9999-12-31, п", "П").replace("name", message.from_user.full_name).replace("date", f'{user.blocked_until.date()}'))
    return await message.answer(user_texts.greetings.replace('full_name', message.from_user.full_name), reply_markup=user_keyboards.main_menu)

@new_user_router.message(user_states.Registration.phone)
async def handle_user_registration(message: Message, state: FSMContext, professor_bot, professor_client):
    user_id = message.from_user.id
    result = await CHAT_NOT_BANNED_FILTER(user_id)
    if not result: return await message.answer(user_texts.banned_in_channel)
    if not message.contact: return await message.answer(user_texts.verify_phone.replace('*', message.from_user.full_name), reply_markup=user_keyboards.phone)

    phone = message.contact.phone_number
    await state.clear()
    await professor_bot.create_user(message.from_user.id, phone)
    await (await message.answer('Проверка пройдена успешно ✅', reply_markup=ReplyKeyboardRemove())).delete()
    return await handle_user_start(message, state)

@new_user_router.message(user_states.CalculateClicks.cartridge_volume, lambda message: message.text and message.text.strip())
async def handle_cartridge_volume(message: Message, state: FSMContext):
    try: amount = float(message.text.strip().replace(',', '.'))
    except: return await message.answer(user_texts.num_format_error, reply_markup=user_keyboards.back)
    await state.update_data(cartridge_volume=amount)
    await state.set_state(user_states.CalculateClicks.cartridge_amount)
    return await message.answer(user_texts.cartridge_amount, reply_markup=user_keyboards.back)


@new_user_router.message(user_states.CalculateClicks.cartridge_amount, lambda message: message.text and message.text.strip())
async def handle_cartridge_amount(message: Message, state: FSMContext):
    try: amount = float(message.text.strip().replace(',', '.'))
    except: return await message.answer(user_texts.num_format_error, reply_markup=user_keyboards.back)
    await state.update_data(cartridge_amount_mg=amount)
    await state.set_state(user_states.CalculateClicks.desired_dosage)
    return await message.answer(user_texts.desired_dosage, reply_markup=user_keyboards.back)


@new_user_router.message(user_states.CalculateClicks.desired_dosage, lambda message: message.text and message.text.strip())
async def handle_desired_dosage_clicks(message: Message, state: FSMContext):
    try: dosage_mg = float(message.text.strip().replace(',', '.'))
    except: return await message.answer(user_texts.num_format_error, reply_markup=user_keyboards.back)
    state_data = await state.get_data()
    cartridge_amount_mg = state_data['cartridge_amount_mg']
    cartridge_volume = state_data['cartridge_volume']

    mg_per_click = (cartridge_amount_mg / cartridge_volume) * 0.01
    click_amount_exact = dosage_mg / mg_per_click

    response_text = (f"<b>Входные данные</b>\n"
                     f"Объем картриджа (мл): <i>{_fmt(cartridge_volume)}</i>\n"
                     f"Количество вещества в картридже (мг): <i>{_fmt(cartridge_amount_mg)}</i>\n"
                     f"Желаемая дозировка вещества (мг): <i>{_fmt(dosage_mg)}</i>\n\n"
                     f"<b>Результаты</b>\n"
                     f"Количество вводимого вещества на 1 щелчок: ({_fmt(cartridge_amount_mg)}мг ÷ {_fmt(cartridge_volume)}мл) • 0.01мл = {_fmt(mg_per_click)}мг\n\n"
                     f"<b>ИТОГО КОЛИЧЕСТВО ЩЕЛЧКОВ: {_fmt(dosage_mg)}мг ÷ {_fmt(mg_per_click)}мг = {_fmt(click_amount_exact)}</b>")

    await message.answer(response_text, reply_markup=user_keyboards.backk)
    return await state.clear()


@new_user_router.message(user_states.CalculateDivisions.vial_amount, lambda message: message.text and message.text.strip())
async def handle_vial_amount(message: Message, state: FSMContext):
    try: amount = float(message.text.strip().replace(',', '.'))
    except: return await message.answer(user_texts.num_format_error, reply_markup=user_keyboards.back)
    await state.update_data(vial_amount_mg=amount)
    await state.set_state(user_states.CalculateDivisions.water_volume)
    return await message.answer(user_texts.water_volume, reply_markup=user_keyboards.back)


@new_user_router.message(user_states.CalculateDivisions.water_volume, lambda message: message.text and message.text.strip())
async def handle_water_volume(message: Message, state: FSMContext):
    try: amount = float(message.text.strip().replace(',', '.'))
    except: return await message.answer(user_texts.num_format_error, reply_markup=user_keyboards.back)
    await state.update_data(water_volume=amount)
    await state.set_state(user_states.CalculateDivisions.desired_dosage)
    return await message.answer(user_texts.desired_dosage, reply_markup=user_keyboards.back)


@new_user_router.message(user_states.CalculateDivisions.desired_dosage, lambda message: message.text and message.text.strip())
async def handle_desired_dosage_divisions(message: Message, state: FSMContext):
    try: desired_dosage_mg = float(message.text.strip().replace(",", "."))
    except: return await message.answer(user_texts.num_format_error, reply_markup=user_keyboards.back)

    state_data = await state.get_data()
    vial_amount_mg = state_data["vial_amount_mg"]
    water_volume = state_data["water_volume"]

    vial_mcg = vial_amount_mg * 1000.0
    dosage_mcg = desired_dosage_mg * 1000.0

    mcg_per_ml = vial_mcg / water_volume
    mcg_per_division = mcg_per_ml * 0.01  # 0.01 ml == 1 "единица"
    divisions = dosage_mcg / mcg_per_division  # может быть float из-за деления

    total_units = int(round(divisions))  # 500.0 -> 500
    full_syringes = total_units // 100
    remainder_units = total_units % 100

    def ru_plural(n: int, one: str, two_four: str, five: str) -> str:
        n = abs(n) % 100
        n1 = n % 10
        if 11 <= n <= 19: return five
        if n1 == 1: return one
        if 2 <= n1 <= 4: return two_four
        return five

    caption = "Визуализация делений на шприце"

    if full_syringes > 0 and remainder_units > 0:
        caption += (
            f"\n<i>{full_syringes} {ru_plural(full_syringes, 'полный шприц', 'полных шприца', 'полных шприцев')}"
            f" + 1 на {remainder_units} {ru_plural(remainder_units, 'единицу', 'единицы', 'единиц')}</i>"
        )
    elif full_syringes > 0 and remainder_units == 0: caption += f"\n<i>{full_syringes} {ru_plural(full_syringes, 'полный шприц', 'полных шприца', 'полных шприцев')}</i>"

    if full_syringes > 0: value_for_plot = remainder_units if remainder_units > 0 else 100
    else: value_for_plot = total_units

    fpath = plot_filled_scale(value_for_plot)
    await message.answer_photo(FSInputFile(fpath), caption=caption)
    fpath.unlink()

    response_text = (
        f"<b>Входные данные</b>\n"
        f"Количество вещества во флаконе (мг): <i>{_fmt(vial_amount_mg)}</i>\n"
        f"Объем воды (мл): <i>{_fmt(water_volume)}</i>\n"
        f"Желаемая дозировка вещества (мг): <i>{_fmt(desired_dosage_mg)}</i>\n\n"
        f"<b>Результаты</b>\n"
        f"Концентрация после разведения: {_fmt(vial_amount_mg)}мг ÷ {_fmt(water_volume)}мл = {_fmt(vial_amount_mg / water_volume)}мг/мл\n"
        f"Количество вещества на 1 единицу (0.01мл): {_fmt(vial_amount_mg / water_volume)}мг/мл • 0.01мл = {_fmt((vial_amount_mg / water_volume) * 0.01)}мг\n\n"
        f"<b>ИТОГО НУЖНО НАБРАТЬ ЕДИНИЦ: {_fmt(desired_dosage_mg)}мг ÷ {_fmt((vial_amount_mg / water_volume) * 0.01)}мг = {total_units}</b>\n"
    )

    await message.answer(response_text, reply_markup=user_keyboards.backk)
    return await state.clear()


@new_user_router.message(user_states.Graph.dosage, lambda message: message.text and message.text.strip())
async def handle_dosage_graph(message: Message, state: FSMContext):
    try: amount = float(message.text.strip().replace(',', '.'))
    except: return await message.answer(user_texts.num_format_error, reply_markup=user_keyboards.back)
    await state.update_data(dose_mg=amount)
    await state.set_state(user_states.Graph.course_length_weeks)
    return await message.answer(user_texts.course_length_weeks, reply_markup=user_keyboards.back)


@new_user_router.message(user_states.Graph.course_length_weeks, lambda message: message.text and message.text.strip())
async def handle_course_length_weeks(message: Message, state: FSMContext):
    try: amount = float(message.text.strip().replace(',', '.'))
    except: return await message.answer(user_texts.num_format_error, reply_markup=user_keyboards.back)
    await state.update_data(weeks=amount)
    await state.set_state(user_states.Graph.course_interval_days)
    return await message.answer(user_texts.course_interval_days, reply_markup=user_keyboards.back)


@new_user_router.message(user_states.Graph.course_interval_days, lambda message: message.text and message.text.strip())
async def handle_course_interval_days(message: Message, state: FSMContext):
    try: interval_days = float(message.text.strip().replace(',', '.'))
    except: return await message.answer(user_texts.num_format_error, reply_markup=user_keyboards.back)

    state_data = await state.get_data()
    drug_key = state_data['drug_key']
    weeks = state_data['weeks']
    dose_mg = state_data['dose_mg']

    fpath = DATA_DIR / generate_drug_graphs(drug_key, weeks, dose_mg, interval_days)
    caption = (
        f'График <b>содержания пептида в крови</b> на протяжении курса по параметрам\n'
        f'Пептид: <i>{drug_key.capitalize()}</i>\n'
        f'Длительность курса (в неделях): <i>{_fmt(weeks)}</i>\n'
        f'Интервал между уколами (в днях): <i>{_fmt(interval_days)}</i>\n'
        f'Дозировка пептида (мг): <i>{_fmt(dose_mg)}</i>\n'
    )
    await message.answer_photo(FSInputFile(fpath), caption=caption)
    fpath.unlink()
    return await handle_user_start(message, state)

@new_user_router.message(Command('new_chat'))
async def handle_new_chat(message: Message, state: FSMContext, professor_client):
    user_id = message.from_user.id
    result = await CHAT_NOT_BANNED_FILTER(user_id)
    if not result: return await message.answer(user_texts.banned_in_channel)
    thread_id = await professor_client.create_thread()
    async with get_session() as session: await update_user(session, message.from_user.id, UserUpdate(thread_id=thread_id))
    await state.update_data(thread_id=thread_id)
    return await message.answer(user_texts.new_chat)

@new_user_router.callback_query()
async def handle_user_call(call: CallbackQuery, state: FSMContext):
    data = call.data.removeprefix("user:").split(":")
    state_data = await state.get_data()
    if data[0] == "about": return await about(call.message)
    elif data[0] == "offer": return await offer(call.message)
    elif data[0] == "ai":
        if data[1] == "start":
            await call.message.edit_text(user_texts.pick_ai, reply_markup=user_keyboards.pick_ai)
        elif data[1] == "free":
            await state.update_data(assistant_id=PROFESSOR_ASSISTANT_ID)
            await call.message.edit_text(user_texts.pick_free, reply_markup=user_keyboards.back)
        elif data[1] == "premium":
            await state.update_data(assistant_id=NEW_ASSISTANT_ID)
            await call.message.edit_text(user_texts.pick_premium, reply_markup=user_keyboards.back)

    elif data[0] == "calculators": await call.message.edit_text(user_texts.calculators_start, reply_markup=user_keyboards.calculators_menu)
    elif data[0] == "clicks":
        if data[1] == "start":
            await call.message.edit_text(user_texts.cartridge_volume, reply_markup=user_keyboards.cartridge_volume)
            await state.set_state(user_states.CalculateClicks.cartridge_volume)

        elif data[1] == 'cartridge_volume':
            await state.clear()
            await state.update_data(cartridge_volume=3)
            await state.set_state(user_states.CalculateClicks.cartridge_amount)
            await call.message.edit_text(user_texts.cartridge_amount, reply_markup=user_keyboards.back)

    elif data[0] == "divisions":
        if data[1] == 'start':
            await call.message.edit_text(user_texts.vial_amount, reply_markup=user_keyboards.back)
            await state.set_state(user_states.CalculateDivisions.vial_amount)

    elif data[0] == "graph":
        if data[1] == 'start': await call.message.edit_text(user_texts.choose_peptide, reply_markup=user_keyboards.peptides_keyboard)
        elif data[1] == "drug":
            drug_key = data[2]
            await state.update_data(drug_key=drug_key)
            await state.set_state(user_states.Graph.dosage)
            await call.message.edit_text(user_texts.dosage, reply_markup=user_keyboards.back)

    elif data[0] == "main_menu": await call.message.edit_text(user_texts.greetings.replace('full_name', call.from_user.full_name), reply_markup=user_keyboards.main_menu)
    elif data[0] == "main_menuu":
        await call.message.edit_reply_markup(reply_markup=None)
        await call.message.answer(user_texts.greetings.replace('full_name', call.from_user.full_name), reply_markup=user_keyboards.main_menu)

@new_user_router.message(lambda message: message.text)
@with_typing
async def handle_text_message(message: Message, state: FSMContext, professor_bot, professor_client):
    user_id = message.from_user.id
    result = await CHAT_NOT_BANNED_FILTER(user_id)
    if not result: return await message.answer(user_texts.banned_in_channel)

    async with get_session() as session: user = await get_user(session, 'tg_id', user_id)
    if not user: return await handle_user_start(message, state, professor_bot, professor_client)
    if user.blocked_until and user.blocked_until.replace(tzinfo=MOSCOW_TZ) > datetime.now(MOSCOW_TZ): return await message.answer(user_texts.banned_until.replace("Блокировка до 9999-12-31, п", "П").replace("name", message.from_user.full_name).replace("date", f'{user.blocked_until.date()}'))

    state_data = await state.get_data()
    assistant_id = state_data.get("assistant_id", None)
    if not assistant_id:
        assistant_id = PROFESSOR_ASSISTANT_ID
        await state.update_data(assistant_id=assistant_id)
        await _notify_user(message, user_texts.pick_fallback_free, 10)

    elif assistant_id == NEW_ASSISTANT_ID and user.premium_requests <= 0: return await message.answer(user_texts.premium_limit_0, reply_markup=user_keyboards.only_free)

    response = await professor_client.send_message(message.text, user.thread_id, assistant_id)
    async with get_session() as session:
        await increment_tokens(session, message.from_user.id, response['input_tokens'], response['output_tokens']),
        await write_usage(session, message.from_user.id, response['input_tokens'], response['output_tokens'], BOT_KEYWORDS[assistant_id])
        if assistant_id == NEW_ASSISTANT_ID:
            user_update = UserUpdate(premium_requests=user.premium_requests-1)
            user = await update_user(session, message.from_user.id, user_update)

    return await professor_bot.parse_response(response, message, back_menu=True)
