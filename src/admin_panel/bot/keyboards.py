from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

class ProductPhotoDoses(InlineKeyboardMarkup):
    def __init__(self, doses: dict[str, str], product_onec_id: str):
        doses = dict(sorted(doses.items(), key=lambda x: x[1]))
        buttons = [InlineKeyboardButton(text=doses[onec_id], callback_data=f"product_photos:{onec_id}") for onec_id in doses]
        super().__init__(inline_keyboard=[buttons[i: i+2] for i in range(0, len( buttons), 2)] + [[InlineKeyboardButton(text="Удалить основное фото", callback_data=f"delete_photo:{product_onec_id}")]])


class DeletePhoto(InlineKeyboardMarkup):
    def __init__(self, onec_id: str):
        super().__init__(inline_keyboard=[
            [InlineKeyboardButton(text="🗑️ Удалить фото", callback_data=f"delete_photo:{onec_id}")]
        ])
