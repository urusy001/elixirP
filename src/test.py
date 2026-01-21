import re
import phonenumbers

from typing import Optional, Iterable
from phonenumbers import NumberParseException, PhoneNumberFormat


def _clean(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("+"): return "+" + re.sub(r"\D", "", raw[1:])
    return re.sub(r"\D", "", raw)


def normalize_to_e164(raw: str, default_regions: Iterable[str] = ("US", "AM", "RU", "UA", "BY", "AZ", "KZ", "KG", "MD", "TJ", "TM", "UZ", "GE")) -> Optional[str]:
    s = _clean(raw)
    if not s: return None

    if s.startswith("+"):
        try:
            n = phonenumbers.parse(s, None)
            return phonenumbers.format_number(n, PhoneNumberFormat.E164) if phonenumbers.is_valid_number(n) else None
        except NumberParseException: return None

    for region in default_regions:
        try:
            n = phonenumbers.parse(s, region)
            if phonenumbers.is_valid_number(n): return phonenumbers.format_number(n, PhoneNumberFormat.E164)
        except NumberParseException: continue

    return raw



if __name__ == "__main__":
    print(normalize_to_e164("1 (763) 27-3 0385"))