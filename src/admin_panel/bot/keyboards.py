from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

class ProductPhotoDoses(InlineKeyboardMarkup):
    def __init__(self, doses: dict[str, str], product_onec_id: str):
        doses = dict(sorted(doses.items(), key=lambda x: x[1]))
        buttons = [InlineKeyboardButton(text=doses[onec_id], callback_data=f"product_photos:{onec_id}") for onec_id in doses]
        [print(button.model_dump_json(indent=4)) for button in buttons]
        super().__init__(inline_keyboard=[buttons[i: i+2] for i in range(0, len( buttons), 2)])
