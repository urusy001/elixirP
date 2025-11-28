from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import InputTextMessageContent, InlineQueryResultArticle, Message, InlineQuery, InlineKeyboardMarkup, \
    InlineKeyboardButton, CallbackQuery, WebAppInfo

from config import OWNER_TG_IDS
from src.ai.bot.keyboards.shop_admin import ProductActions
from src.helpers import normalize_html_for_telegram
from src.webapp import get_session
from src.webapp.crud import get_product_with_features
from src.webapp.routes.search import search_products
from src.ai.bot.states import admin_states

router = Router()

@router.message(Command('app'))
@router.message(CommandStart(), lambda message: message.from_user.id not in OWNER_TG_IDS)
async def open_app(message: Message): await message.answer("Приветственный текст!!", reply_markup=open_app)

@router.message(Command('product'), lambda message: message.from_user.id in OWNER_TG_IDS)
async def handle_product(message: Message):
    onec_id = message.text.strip().removeprefix("/product ")
    if not onec_id: await message.answer(f"<b>Ошибка команды</b>: не указан айди товара\n<code>/product айди_товара_номенклатура_1с</code>\n\n<i>Айди товара можно получить используя поиск бота</i>: <code>{'@'+(await message.bot.get_me()).username} search название_товара</code>")
    else:
        async with get_session() as session: product = await get_product_with_features(session, onec_id)
        text = normalize_html_for_telegram(str(product))
        await message.answer(text, reply_markup=ProductActions(onec_id))

@router.inline_query(lambda inline_query: inline_query.query.startswith("search") and inline_query.from_user.id in OWNER_TG_IDS)
async def handle_product_name(inline_query: InlineQuery, state: FSMContext):
    query = inline_query.query.strip().removeprefix("search").strip()
    print(query)
    if not query: return
    await state.set_state(admin_states.MainMenu.search_product)
    async with get_session() as db: data = await search_products(db, q=query, page=0, limit=10)

    results = []
    for idx, item in enumerate(data["results"], start=1):
        results.append(
            InlineQueryResultArticle(
                id=str(idx),
                title=item["name"],
                description=", ".join(f["name"] for f in item["features"]),
                input_message_content=InputTextMessageContent(
                    message_text=f'/product {item["url"].removeprefix("/product/")}',
                ),
            )
        )

    await inline_query.answer(results, cache_time=1)

@router.callback_query(lambda query: query.from_user.id in OWNER_TG_IDS)
async def handle_shopadmin_callback(query: CallbackQuery, state: FSMContext):
    pass
