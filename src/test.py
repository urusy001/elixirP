import re
from typing import Dict, List, Tuple

PRICE_RE = re.compile(
    r"[—\-]\s*([0-9][0-9\s]*)\s*(?:руб\.?|₽)\b",
    flags=re.IGNORECASE
)

ORDER_SPLIT_RE = re.compile(r"(?=^Заказ\s*№\d+)", flags=re.MULTILINE)

ORDER_NO_RE = re.compile(r"^Заказ\s*№(\d+)", flags=re.MULTILINE)


def _extract_prices_rub(text: str) -> List[int]:
    prices = []
    for m in PRICE_RE.finditer(text):
        raw = m.group(1)  # like "10 780"
        prices.append(int(raw.replace(" ", "")))
    return prices


def extract_order_totals(note_text: str) -> List[Tuple[str, int]]:
    """
    Returns list of (order_number, items_total_rub).
    """
    blocks = [b.strip() for b in ORDER_SPLIT_RE.split(note_text.strip()) if b.strip()]
    out: List[Tuple[str, int]] = []

    for block in blocks:
        order_no = "UNKNOWN"
        m = ORDER_NO_RE.search(block)
        if m:
            order_no = m.group(1)

        total = sum(_extract_prices_rub(block))
        out.append((order_no, total))

    return out


# ---------- example ----------
if __name__ == "__main__":
    sample = """Заказ №14859 с сайта ElixirPeptide
Дата заказа: 16.12.2025
Cостав заказа:
1. Cagrilintide 5мг 2шт. — 10 780руб.
2. GBK 20мг+5мг+5мг 1шт. — 3 690руб.
3. SemaSlim 12мг/3мл 1шт. — 6 490руб.

Доставка: Курьер СДЕК: Краснодар, ст-ца Старокорсунская

Имя клиента: Анжелика Здобникова
Номер телефона: +7(902)927-93-33
Email: angela6565@mail.ru

Промо-код: Не указано
Комментарий к заказу: Моя скидка 15%
Доставка Яндекс!!!
Заказ №14848 с сайта ElixirPeptide
Дата заказа: 15.12.2025
Cостав заказа:
1. Tesofensine капсулы 500мкг/60 капсул 2шт. — 8 980руб.
2. BAM-15 капсулы 50мг/60 капсул 1шт. — 18 790руб.
3. MOTS-C Спрей 20мг/10мл 1шт. — 3 590руб.
4. KPV спрей 10мг/10мл 1шт. — 2 790руб.
"""

    for order_no, total in extract_order_totals(sample):
        print(f"Заказ №{order_no}: {total:,} руб.".replace(",", " "))