# Put this into a script file, e.g. src/scripts/sync_cart_contacts.py
# Then run:  python -m src.scripts.sync_cart_contacts
#
# Assumes:
# - carts table already has columns: phone, email
# - update_cart(session, cart_id, CartUpdate(...)) works with these fields
# - AsyncAmoCRM instance is available as `amocrm`
# - get_session() returns AsyncSession context manager

from __future__ import annotations

import asyncio
import re
from typing import Optional, Tuple

from sqlalchemy import select

from src.webapp import get_session
from src.webapp.models import Cart
from src.webapp.crud import update_cart
from src.webapp.schemas import CartUpdate

# import your existing instance
from .client import amocrm  # <- change this import


DEFAULT_STR = "Не указан"


def _norm_str(x: object | None) -> str:
    s = "" if x is None else str(x)
    s = s.strip()
    return s


class _AmoContactExtractMixin:
    @staticmethod
    def _extract_phone_from_contact_obj(contact: dict) -> Optional[str]:
        cfs = contact.get("custom_fields_values") or []
        if not isinstance(cfs, list):
            return None

        for cf in cfs:
            if not isinstance(cf, dict):
                continue
            code = (cf.get("field_code") or "").upper()
            name = (cf.get("field_name") or "").lower()

            if code == "PHONE" or "phone" in name or "тел" in name:
                values = cf.get("values") or []
                if not isinstance(values, list):
                    continue
                for v in values:
                    val = (v or {}).get("value")
                    if isinstance(val, str) and val.strip():
                        return val.strip()

        return None

    @staticmethod
    def _extract_email_from_contact_obj(contact: dict) -> Optional[str]:
        cfs = contact.get("custom_fields_values") or []
        if not isinstance(cfs, list):
            return None
        for cf in cfs:
            if not isinstance(cf, dict):
                continue
            code = (cf.get("field_code") or "").upper()
            name = (cf.get("field_name") or "").lower()
            if code == "EMAIL" or "email" in name or "почта" in name:
                values = cf.get("values") or []
                if not isinstance(values, list):
                    continue
                for v in values:
                    val = (v or {}).get("value")
                    if isinstance(val, str) and "@" in val:
                        return val.strip()
        return None


async def _get_lead_for_cart_id(cart_id: int) -> Optional[dict]:
    """
    Find lead by exact title:
      "Заказ №{cart_id} с Приложения ТГ"
    and return lead dict (with contacts embedded if possible).
    """
    expected = f"Заказ №{cart_id} с Приложения ТГ"
    # fast filter token
    needle = f"№{cart_id} "

    page = 1
    limit = 50
    max_pages = 20

    # also allow strict match by regex in case there are extra spaces
    rx = re.compile(rf"^Заказ\s+№\s*{re.escape(str(cart_id))}\s+с\s+Приложения\s+ТГ$", re.IGNORECASE)

    while page <= max_pages:
        data = await amocrm.get(
            "/api/v4/leads",
            params={
                "query": needle,
                "limit": limit,
                "page": page,
                "with": "contacts",
            },
        )

        leads = (data.get("_embedded") or {}).get("leads") or []
        if not leads:
            return None

        for lead in leads:
            name = (lead.get("name") or "").strip()
            # Prefer exact match
            if name == expected or rx.search(name):
                return lead

        page += 1

    return None


async def _extract_contact_from_lead(lead: dict) -> Tuple[Optional[str], Optional[str]]:
    """
    Try to extract phone/email from linked contacts.
    If lead has embedded contacts with custom_fields_values, use them.
    Otherwise fetch each contact by id.
    """
    embedded = lead.get("_embedded") or {}
    contacts = embedded.get("contacts") or lead.get("contacts") or []
    if not isinstance(contacts, list) or not contacts:
        return None, None

    # main contact first
    ordered = sorted(contacts, key=lambda c: 0 if isinstance(c, dict) and c.get("is_main") else 1)

    phone: Optional[str] = None
    email: Optional[str] = None

    for c in ordered:
        if isinstance(c, dict) and c.get("custom_fields_values"):
            if email is None:
                email = _AmoContactExtractMixin._extract_email_from_contact_obj(c)
            if phone is None:
                phone = _AmoContactExtractMixin._extract_phone_from_contact_obj(c)
            if phone or email:
                return phone, email

        cid = None
        if isinstance(c, dict):
            cid = c.get("id") or c.get("contact_id")

        if cid:
            contact = await amocrm.get(f"/api/v4/contacts/{cid}")
            if email is None:
                email = _AmoContactExtractMixin._extract_email_from_contact_obj(contact)
            if phone is None:
                phone = _AmoContactExtractMixin._extract_phone_from_contact_obj(contact)

            if phone or email:
                return phone, email

    return phone, email


async def sync_cart_contacts_from_amocrm() -> None:
    # 1) get all cart ids
    async with get_session() as session:
        res = await session.execute(select(Cart.id))
        cart_ids = res.scalars().all()

    updated = 0
    not_found = 0

    for cart_id in cart_ids:
        try:
            lead = await _get_lead_for_cart_id(int(cart_id))
            if not lead:
                not_found += 1
                continue

            phone, email = await _extract_contact_from_lead(lead)

            phone = _norm_str(phone) or DEFAULT_STR
            email = _norm_str(email) or DEFAULT_STR

            async with get_session() as session:
                await update_cart(session, int(cart_id), CartUpdate(phone=phone, email=email))

            updated += 1

        except Exception as e:
            # keep going
            print(f"[ERR] cart_id={cart_id}: {e}")

    print(f"Done. updated={updated}, leads_not_found={not_found}, total={len(cart_ids)}")


if __name__ == "__main__":
    asyncio.run(sync_cart_contacts_from_amocrm())