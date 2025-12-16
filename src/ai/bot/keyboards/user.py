from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

from src.ai.calc import PEPTIDE_DATA

back_button = InlineKeyboardButton(text="🔙 Назад в главное меню", callback_data="user:main_menu")
back = InlineKeyboardMarkup(inline_keyboard=[
    [back_button]
])
backk = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔙 Назад в главное меню", callback_data="user:main_menuu")]
])

phone = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True, keyboard=[
    [KeyboardButton(text='Подтвердить', request_contact=True)]
])

open_app = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🛒 Открыть магазин 🛍️", web_app=WebAppInfo(url="https://elixirpeptides.devsivanschostakov.org"))],
    [InlineKeyboardButton(text="📑 Оферта", callback_data="user:offer"), InlineKeyboardButton(text="Данные ИП 👨🏻‍💻", callback_data="user:about")],
    [back_button]
])

main_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='🤖 ИИ Ассистенты 🧠', callback_data="user:ai:start"),
     InlineKeyboardButton(text='✖️ Калькуляторы ➗', callback_data="user:calculators")],
    [InlineKeyboardButton(text="🛒 Открыть магазин 🛍️", web_app=WebAppInfo(url="https://elixirpeptides.devsivanschostakov.org"))],
    [InlineKeyboardButton(text="📑 Оферта", callback_data="user:offer"), InlineKeyboardButton(text="Данные ИП 👨🏻‍💻", callback_data="user:about")]
])

pick_ai = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='✨ИИ-профессор', callback_data="user:ai:premium"),
     InlineKeyboardButton(text='⚡️ИИ-эксперт', callback_data="user:ai:free")],
    [back_button]
])

only_free = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='⚡️ИИ-эксперт', callback_data="user:ai:free")],
    [back_button]
])

calculators_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🖊️ Посчитать щелчки ручки ➗", callback_data="user:clicks:start")],
    [InlineKeyboardButton(text="💉 Посчитать деления шприца ✖️", callback_data="user:divisions:start")],
    [InlineKeyboardButton(text="📈 График содержания в крови 🩸", callback_data="user:graph:start")],
    [back_button]
])

graph_dosage_unit = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='Миллиграмм (мг)', callback_data="user:graph:dosage_unit:1000"),
     InlineKeyboardButton(text='Микрограмм (мкг)', callback_data="user:graph:dosage_unit:1")],
    [InlineKeyboardButton(text='🧮 К остальным калькуляторам', callback_data="user:calculators")],
    [back_button]
])

cartridge_volume = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='Объем по умолчанию (3 мл)', callback_data="user:clicks:cartridge_volume")],
    [InlineKeyboardButton(text='🧮 К остальным калькуляторам', callback_data="user:calculators")],
    [back_button]
])

cartridge_unit = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='Миллиграмм (мг)', callback_data="user:clicks:cartridge_unit:1000"),
     InlineKeyboardButton(text='Микрограмм (мкг)', callback_data="user:clicks:cartridge_unit:1")],
    [InlineKeyboardButton(text='🧮 К остальным калькуляторам', callback_data="user:calculators")],
    [back_button]
])

vial_unit = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='Миллиграмм (мг)', callback_data="user:divisions:vial_unit:1000"),
     InlineKeyboardButton(text='Микрограмм (мкг)', callback_data="user:divisions:vial_unit:1")],
    [InlineKeyboardButton(text='🧮 К остальным калькуляторам', callback_data="user:calculators")],
    [back_button]
])

clicks_desired_dosage_unit = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='Миллиграмм (мг)', callback_data="user:clicks:dosage_unit:1000"),
     InlineKeyboardButton(text='Микрограмм (мкг)', callback_data="user:clicks:dosage_unit:1")],
    [InlineKeyboardButton(text='🧮 К остальным калькуляторам', callback_data="user:calculators")],
    [back_button]
])

divisions_desired_dosage_unit = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='Миллиграмм (мг)', callback_data="user:divisions:dosage_unit:1000"),
     InlineKeyboardButton(text='Микрограмм (мкг)', callback_data="user:divisions:dosage_unit:1")],
    [InlineKeyboardButton(text='🧮 К остальным калькуляторам', callback_data="user:calculators")],
    [back_button]
])

buttons = [InlineKeyboardButton(text=drug.name, callback_data=f"user:graph:drug:{key}") for key, drug in PEPTIDE_DATA.items()]
peptides_keyboard = InlineKeyboardMarkup(inline_keyboard=[buttons[i: i+2] for i in range(0, len(buttons), 2)]+[[back_button]])
calc_back = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='🧮 К остальным калькуляторам', callback_data="user:calculators")],
    [back_button]
])