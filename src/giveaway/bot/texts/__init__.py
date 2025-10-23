from src.webapp.models import Giveaway
from . import admin as admin_texts
from . import user as user_texts


def get_giveaway_text(giveaway: Giveaway):
    giveaway_text = f'🎉 <b>{giveaway.name.upper()}</b> 🥳\n\n{giveaway.description + "\n\n" or ""}🎁 <b>Что можно выиграть?</b>'
    place_texts = {
        1: "🥇 1 место",
        2: "🥈 2 место",
        3: "🥉 3 место"
    }
    for place, prize in giveaway.prize.items(): giveaway_text += f'\n{place_texts.get(int(place), f"🏅 {place} Место")} — {prize}'

    giveaway_text += '\n\n<b>Выполняйте условия и проверяй их кнопками ниже</b> ⬇️\nВы будете записаны в участники розыгрыша после выполнения всех условий'
    return giveaway_text
