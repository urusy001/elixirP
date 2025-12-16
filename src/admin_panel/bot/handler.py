import aiofiles
from aiogram import Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    InputTextMessageContent,
    InlineQueryResultArticle,
    Message,
    InlineQuery,
    CallbackQuery,
    FSInputFile,
    InlineKeyboardMarkup,
)

from config import OWNER_TG_IDS, IMAGES_DIR
from src.admin_panel.bot import texts, keyboards, states
from src.webapp import get_session
from src.webapp.routes.search import search_products

# ✅ CRUD imports you will add (see below)
from src.webapp.crud import (
    get_product_with_features,
    create_tg_category,
    list_tg_categories,
    get_tg_category_by_name,
    delete_tg_category,
    add_tg_category_to_product,
    remove_tg_category_from_product,
)

from src.webapp.schemas import TgCategoryCreate

router = Router()

admin_filter = lambda obj: obj.from_user and obj.from_user.id in OWNER_TG_IDS and obj.chat.type == ChatType.PRIVATE
admin_call_filter = lambda obj: obj.from_user and obj.from_user.id in OWNER_TG_IDS and obj.message.chat.type == ChatType.PRIVATE
admin_inline_filter = lambda obj: obj.from_user and obj.from_user.id in OWNER_TG_IDS and obj.chat_type == ChatType.PRIVATE

router.message.filter(admin_filter)
router.callback_query.filter(admin_call_filter)
router.inline_query.filter(admin_inline_filter)


async def __handle_product_message(onec_id: str, message: Message, state: FSMContext):
    if not onec_id:
        await message.answer(texts.photo_command_error.replace("username", (await message.bot.get_me()).username))
        await message.delete()
        return

    await state.update_data(product_onec_id=onec_id)
    await state.set_state(states.ProductActions.set_product_photo)

    async with get_session() as session:
        product = await get_product_with_features(session, onec_id)

    photo_path = IMAGES_DIR / f"{onec_id}.png"
    if photo_path.exists():
        await message.answer_photo(FSInputFile(photo_path), caption=texts.product_caption.replace("name", product.name))

    doses = {feature.onec_id: feature.name for feature in product.features}
    await state.update_data(doses=doses)

    await message.answer(
        texts.product_main_photo.replace("name", product.name),
        reply_markup=keyboards.ProductPhotoDoses(doses, product.onec_id),
    )
    await message.delete()


async def __handle_photo(onec_id: str, message: Message, state: FSMContext):
    if not onec_id:
        await message.answer("Ошибочка")
        return

    photo = message.photo[-1]
    file = await message.bot.get_file(photo.file_id)
    file_bytes = await message.bot.download(file)
    file_bytes = file_bytes.getvalue()

    photo_path = IMAGES_DIR / f"{onec_id}.png"
    async with aiofiles.open(photo_path, "wb") as f:
        await f.write(file_bytes)

    await message.answer("Фото успешно сохранено")
    await state.clear()


@router.message(Command("photo"))
async def handle_photo(message: Message, state: FSMContext):
    onec_id = message.text.removeprefix("/photo").strip()
    await __handle_product_message(onec_id, message, state)


@router.message(lambda message: message.photo, states.ProductActions.set_product_photo)
async def handle_product_photos(message: Message, state: FSMContext):
    state_data = await state.get_data()
    product_onec_id = state_data.get("product_onec_id")
    await __handle_photo(product_onec_id, message, state)


@router.message(lambda message: message.photo, states.ProductActions.set_feature_photo)
async def handle_feature_photo(message: Message, state: FSMContext):
    state_data = await state.get_data()
    feature_onec_id = state_data.get("feature_onec_id")
    await __handle_photo(feature_onec_id, message, state)


# =========================
# TG CATEGORIES ADMIN
# =========================

@router.message(Command("create_category"))
async def handle_create_category(message: Message, state: FSMContext):
    category_name = message.text.removeprefix("/create_category").strip()
    if not category_name:
        await message.answer("Добавьте название: <code>/create_category Название</code>")
        return

    category_name = category_name.strip()

    async with get_session() as session:
        category = await create_tg_category(session, TgCategoryCreate(name=category_name))

    await message.answer(
        f"✅ Категория <b>{category.name}</b> создана.\nВыберите её или управляйте кнопками ниже:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [keyboards.SetCategory(category.name).inline_keyboard[0][0]],
        ]),
    )


@router.message(Command("categories"))
async def handle_categories(message: Message, state: FSMContext):
    async with get_session() as session:
        categories = await list_tg_categories(session)

    if not categories:
        await message.answer("Категорий нет. Создайте: <code>/create_category Название</code>")
        return

    buttons = [keyboards.SetCategory(c.name) for c in categories]
    kb = InlineKeyboardMarkup(inline_keyboard=[buttons[i: i + 2] for i in range(0, len(buttons), 2)])
    await message.answer("📦 Выберите категорию:", reply_markup=kb)


@router.message(Command("delete_category"))
async def handle_delete_category_cmd(message: Message, state: FSMContext):
    category_name = message.text.removeprefix("/delete_category").strip()
    if not category_name:
        await message.answer("Укажите категорию: <code>/delete_category Название</code>")
        return

    async with get_session() as session:
        category = await get_tg_category_by_name(session, category_name)
        if not category:
            await message.answer("Категория не найдена.")
            return
        await delete_tg_category(session, category)

    await message.answer(f"🗑️ Категория <b>{category_name}</b> удалена.")


@router.message(Command("add_category"))
async def handle_add_category_to_product(message: Message, state: FSMContext):
    args = message.text.removeprefix("/add_category").strip().split(maxsplit=1)
    if len(args) != 2:
        await message.answer("Формат: <code>/add_category Категория ONEC_ID_товара</code>")
        return

    category_name, product_onec_id = args[0], args[1].strip()

    async with get_session() as session:
        category = await get_tg_category_by_name(session, category_name)
        if not category:
            await message.answer("Категория не найдена.")
            return

        await add_tg_category_to_product(session, product_onec_id=product_onec_id, tg_category_id=category.id)

    await message.answer(f"✅ Добавлено: <b>{product_onec_id}</b> → <b>{category.name}</b>")


@router.message(Command("remove_category"))
async def handle_remove_category_from_product(message: Message, state: FSMContext):
    args = message.text.removeprefix("/remove_category").strip().split(maxsplit=1)
    if len(args) != 2:
        await message.answer("Формат: <code>/remove_category Категория ONEC_ID_товара</code>")
        return

    category_name, product_onec_id = args[0], args[1].strip()

    async with get_session() as session:
        category = await get_tg_category_by_name(session, category_name)
        if not category:
            await message.answer("Категория не найдена.")
            return

        await remove_tg_category_from_product(session, product_onec_id=product_onec_id, tg_category_id=category.id)

    await message.answer(f"➖ Удалено: <b>{product_onec_id}</b> ⟵ <b>{category.name}</b>")


# =========================
# INLINE QUERIES (add/remove product to current category)
# =========================

@router.inline_query(lambda q: q.query.startswith("addcat"))
async def inline_addcat(inline_query: InlineQuery, state: FSMContext):
    st = await state.get_data()
    category_name = st.get("category_name")
    if not category_name:
        return await inline_query.answer([
            InlineQueryResultArticle(
                id="0",
                title="Сначала выберите категорию",
                input_message_content=InputTextMessageContent(message_text="/categories"),
            )
        ], cache_time=1)

    query = inline_query.query.removeprefix("addcat").strip()
    if not query:
        return

    async with get_session() as db:
        data = await search_products(db, q=query, page=0, limit=10)

    results = []
    for idx, item in enumerate(data["results"], start=1):
        onec_id = item["url"].removeprefix("/product/")
        results.append(
            InlineQueryResultArticle(
                id=str(idx),
                title=item["name"],
                description=", ".join(f["name"] for f in item["features"]),
                input_message_content=InputTextMessageContent(
                    message_text=f"/add_category {category_name} {onec_id}",
                ),
            )
        )

    await inline_query.answer(results, cache_time=1)


@router.inline_query(lambda q: q.query.startswith("rmcat"))
async def inline_rmcat(inline_query: InlineQuery, state: FSMContext):
    st = await state.get_data()
    category_name = st.get("category_name")
    if not category_name:
        return await inline_query.answer([
            InlineQueryResultArticle(
                id="0",
                title="Сначала выберите категорию",
                input_message_content=InputTextMessageContent(message_text="/categories"),
            )
        ], cache_time=1)

    query = inline_query.query.removeprefix("rmcat").strip()
    if not query:
        return

    async with get_session() as db:
        data = await search_products(db, q=query, page=0, limit=10)

    results = []
    for idx, item in enumerate(data["results"], start=1):
        onec_id = item["url"].removeprefix("/product/")
        results.append(
            InlineQueryResultArticle(
                id=str(idx),
                title=item["name"],
                description=", ".join(f["name"] for f in item["features"]),
                input_message_content=InputTextMessageContent(
                    message_text=f"/remove_category {category_name} {onec_id}",
                ),
            )
        )

    await inline_query.answer(results, cache_time=1)


@router.inline_query(lambda inline_query: inline_query.query.startswith("photo"))
async def set_product_photo(inline_query: InlineQuery):
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

# =========================
# CALLBACKS
# =========================

@router.callback_query()
async def handle_callback(call: CallbackQuery, state: FSMContext):
    parts = (call.data or "").split(":")
    if not parts:
        return

    if parts[0] == "product_photos":
        state_data = await state.get_data()
        doses = state_data.get("doses", {})
        feature_onec_id = parts[1]

        photo_path = IMAGES_DIR / f"{feature_onec_id}.png"
        if photo_path.exists():
            await call.message.answer_photo(FSInputFile(photo_path), caption=texts.feature_caption)
            await call.message.answer(
                "Нажмите кнопку ниже, чтоб удалить фото для дозировки",
                reply_markup=keyboards.DeletePhoto(feature_onec_id),
            )

        await state.set_state(states.ProductActions.set_feature_photo)
        await state.update_data(feature_onec_id=feature_onec_id)

    elif parts[0] == "delete_photo":
        onec_id = parts[1]
        photo_path = IMAGES_DIR / f"{onec_id}.png"
        if photo_path.exists():
            photo_path.unlink()
            await call.message.edit_text("Фото успешно удалено", reply_markup=None)

    elif parts[0] == "set_category":
        category_name = parts[1]

        async with get_session() as db:
            categories = await list_tg_categories(db)

        buttons = [keyboards.SetCategory(c.name) for c in categories if c.name != category_name]
        kb = InlineKeyboardMarkup(inline_keyboard=[buttons[i: i + 2] for i in range(0, len(buttons), 2)])

        await call.message.edit_text(
            f"✅ Выбрана категория: <b>{category_name}</b>\n"
            f"Теперь можно добавлять/убирать товары:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb.inline_keyboard + keyboards.CategoryActions(category_name).inline_keyboard),
        )

        await state.set_state(states.ProductActions.set_category)
        await state.set_data({"category_name": category_name})

    elif parts[0] == "delete_category":
        category_name = parts[1]
        async with get_session() as db:
            category = await get_tg_category_by_name(db, category_name)
            if not category:
                return await call.answer("Категория не найдена", show_alert=True)
            await delete_tg_category(db, category)

        await call.message.edit_text(f"🗑️ Категория <b>{category_name}</b> удалена.", reply_markup=None)