import aiofiles

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InputTextMessageContent, InlineQueryResultArticle, Message, InlineQuery, CallbackQuery, FSInputFile

from config import OWNER_TG_IDS, IMAGES_DIR
from src.admin_panel.bot import texts, keyboards, states
from src.webapp import get_session
from src.webapp.crud import get_product_with_features
from src.webapp.routes.search import search_products

router = Router()
admin_filter = lambda obj: obj.from_user and obj.from_user.id in OWNER_TG_IDS

async def __handle_product_message(onec_id: str, message: Message, state: FSMContext):
    if not onec_id: await message.answer(texts.photo_command_error.replace('username', (await message.bot.get_me()).username))
    else:
        await state.update_data(product_onec_id=onec_id)
        await state.set_state(states.ProductActions.set_product_photo)
        async with get_session() as session: product = await get_product_with_features(session, onec_id)
        photo_path = IMAGES_DIR / f'{onec_id}.png'
        if photo_path.exists(): await message.answer_photo(FSInputFile(photo_path), caption=texts.product_caption.replace('name', product.name))
        doses = {feature.onec_id: feature.name for feature in product.features}
        await state.update_data(doses=doses)
        await message.answer(texts.product_main_photo.replace('name', product.name), reply_markup=keyboards.ProductPhotoDoses(doses, product.onec_id))

    await message.delete()
async def __handle_photo(onec_id: str, message: Message, state: FSMContext):
    if not onec_id: await message.answer('Ошибочка')
    else:
        photo = message.photo[-1]
        file = await message.bot.get_file(photo.file_id)
        file_bytes = await message.bot.download(file)
        file_bytes = file_bytes.getvalue()
        photo_path = IMAGES_DIR / f'{onec_id}.png'
        async with aiofiles.open(photo_path, 'wb') as f: await f.write(file_bytes)
        await message.answer('Фото успешно сохранено')
        await state.clear()

@router.message(Command('photo'), admin_filter)
async def handle_photo(message: Message, state: FSMContext):
    onec_id = message.text.removeprefix("/photo ").strip()
    await __handle_product_message(onec_id, message, state)

@router.message(lambda message: message.photo, admin_filter, states.ProductActions.set_product_photo)
async def handle_product_photos(message: Message, state: FSMContext):
    state_data = await state.get_data()
    product_onec_id = state_data.get("product_onec_id", None)
    await __handle_photo(product_onec_id, message, state)

@router.message(lambda message: message.photo, admin_filter, states.ProductActions.set_feature_photo)
async def handle_feature_photo(message: Message, state: FSMContext):
    state_data = await state.get_data()
    feature_onec_id = state_data.get("feature_onec_id", None)
    await __handle_photo(feature_onec_id, message, state)

@router.inline_query(lambda inline_query: inline_query.query.startswith("photo") and admin_filter)
async def handle_product_name(inline_query: InlineQuery):
    query = inline_query.query.removeprefix("photo").strip()
    if not query: return
    async with get_session() as db: data = await search_products(db, q=query, page=0, limit=10)

    results = []
    for idx, item in enumerate(data["results"], start=1):
        results.append(
            InlineQueryResultArticle(
                id=str(idx),
                title=item["name"],
                description=", ".join(f["name"] for f in item["features"]),
                input_message_content=InputTextMessageContent(
                    message_text=f'/photo {item["url"].removeprefix("/product/")}',
                ),
            )
        )

    await inline_query.answer(results, cache_time=1)

@router.callback_query(lambda call: call.from_user.id in OWNER_TG_IDS)
async def handle_callback(call: CallbackQuery, state: FSMContext):
    data = call.data.split(':')
    state_data = await state.get_data()
    if data[0] == "product_photos":
        doses = state_data.get("doses", {})
        feature_onec_id = data[1]
        dose_name = doses.get(feature_onec_id, None)
        photo_path = IMAGES_DIR / f'{feature_onec_id}.png'
        if photo_path.exists():
            await call.message.answer_photo(FSInputFile(photo_path), caption=texts.feature_caption)
            await call.message.answer('Нажмите кнопку ниже, чтоб удалить фото для дозировки', reply_markup=keyboards.DeletePhoto(feature_onec_id))
        else: await call.message.answer(f"Дозировака успешно изменена{(' на ' + dose_name) if dose_name else ''}")
        await state.set_state(states.ProductActions.set_feature_photo)
        await state.update_data(feature_onec_id=feature_onec_id)

    elif data[0] == "delete_photo":
        onec_id = data[1]
        photo_path = IMAGES_DIR / f'{onec_id}.png'
        if photo_path.exists():
            photo_path.unlink()
            await call.message.edit_text('Фото успешно удалено', reply_markup=None)
