import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import aiofiles
import httpx
from sqlalchemy import select

from config import MANAGER_USER, MANAGER_PASS, DATA_DIR
from src.giveaway.reviews import endpoints  # keep your original import path
from src.webapp.models import Participant

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)


def _parse_pub_date(s: str) -> Optional[datetime]:
    if not s:
        return None
    s = s.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _naive(dt: datetime) -> datetime:
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


class AsyncElixirClient(httpx.AsyncClient):
    def __init__(self, username: str, password: str):
        super().__init__(follow_redirects=True, timeout=20)
        self.__auth = (username, password)
        self.__logger = logging.getLogger(self.__class__.__name__)

    async def authorize(self) -> bool:
        payload = {
            "login_context": "mgr",
            "modhash": "",
            "returnUrl": "/manager/",
            "username": self.__auth[0],
            "password": self.__auth[1],
            "rememberme": "1",
            "login": "1",
        }
        resp = await self.post(endpoints.LOGIN, data=payload)
        ok = any("PHPSESSID" in c or "modx" in c.lower() for c in self.cookies.keys())
        if ok:
            self.__logger.info("✅ Login successful.")
        else:
            self.__logger.error("❌ Login failed; got login page again.")
            self.__logger.debug(resp.text[:400])
        return ok

    async def _reviews_page(self, page: int) -> Optional[Dict[str, Any]]:
        """GET one page: {status, result:{page, pages, reviews:[...]}}"""
        url = f"{endpoints.REVIEWS}/get.json?page={page}"
        resp = await self.get(url)
        if resp.status_code != 200:
            self.__logger.info(f"Failed to fetch page {page}: {resp.text[:300]}")
            return None
        try:
            return resp.json()
        except Exception:
            self.__logger.info("⚠️ Non-JSON response on reviews page:")
            self.__logger.info(resp.text[:300])
            return None

    async def get_reviews_all(self) -> Optional[List[Dict[str, Any]]]:
        """Fetch ALL reviews across pages and return a flat list."""
        first = await self._reviews_page(1)
        if not first or first.get("status") != "success" or "result" not in first:
            return None

        result = first["result"]
        page = int(result.get("page", 1))
        pages = int(result.get("pages", 1))
        reviews = list(result.get("reviews") or [])

        while page < pages:
            page += 1
            data = await self._reviews_page(page)
            if not data or data.get("status") != "success" or "result" not in data:
                break
            reviews.extend(data["result"].get("reviews") or [])

        return reviews

    async def get_valid_review(
            self,
            *,
            email: str,
            since_dt: datetime,
            min_grade: int,
            min_length: int, session
    ) -> Dict[str, Any]:
        """
        Returns:
          {
            ok: bool,
            reason: str,
            details: dict,
            review: dict | None,
            html_message: str   # HTML (<b>, <i>) for Telegram
          }
        Reasons: no_reviews, no_email_match, only_unpublished, only_older_than_since,
                 low_grade, short_length, low_grade_or_short_length, ok
        """
        """
                Now also checks PostgreSQL to skip already validated review IDs.
                """
        if not await self.authorize():
            return {"ok": False, "reason": "auth_failed", "details": {}, "review": None, "html_message": "Login failed"}

        # Step 1: Get review IDs already stored in participants
        result = await session.execute(select(Participant.review_id).where(Participant.review_id.isnot(None)))
        existing_ids = {r[0] for r in result.fetchall()}
        self.__logger.info(f"Found {len(existing_ids)} existing review IDs in DB.")

        # Step 2: Fetch all site reviews
        all_reviews = await self.get_reviews_all()
        if not all_reviews:
            return {
                "ok": False,
                "reason": "no_reviews",
                "details": {},
                "review": None,
                "html_message": "<b>Отзыв не найден.</b>\n<i>На сайте пока нет опубликованных отзывов.</i>"
            }

        # Step 3: Filter out already-seen ones
        new_reviews = [r for r in all_reviews if r.get("id") not in existing_ids]
        if not new_reviews:
            msg = "<b>Новых отзывов нет.</b>\n<i>Все отзывы уже проверены ранее.</i>"
            self.__logger.info("No new reviews since last check.")
            return {"ok": False, "reason": "no_new_reviews", "details": {}, "review": None, "html_message": msg}

        email_norm = (email or "").strip().lower()
        by_email = [r for r in all_reviews if str(r.get("email", "")).strip().lower() == email_norm]
        if not by_email:
            reason = "no_email_match"
            msg = f"<b>Отзыв не найден.</b>\n<i>Электронная почта {email} отсутствует среди отзывов.</i>"
            self.__logger.info("Не найдено отзывов по email %s", email_norm)
            return {"ok": False, "reason": reason, "details": {"email": email}, "review": None, "html_message": msg}

        published = [r for r in by_email if int(r.get("published", 0)) in [1, 0]]
        if not published:
            reason = "only_unpublished"
            msg = f"<b>Отзыв не опубликован.</b>\n<i>Найден отзыв по адресу {email}, но он еще не опубликован на сайте.</i>"
            self.__logger.info("Найден только неопубликованный отзыв для %s", email_norm)
            return {"ok": False, "reason": reason, "details": {"email": email, "count": len(by_email)}, "review": None,
                    "html_message": msg}

        since_naive = _naive(since_dt)
        with_dates: List[Tuple[datetime, Dict[str, Any]]] = []
        for r in published:
            dt = _parse_pub_date(str(r.get("pub_date", "")))
            if dt:
                with_dates.append((dt, r))
            else:
                self.__logger.debug("Unparseable pub_date id=%s value=%r", r.get("id"), r.get("pub_date"))

        if not with_dates:
            reason = "only_older_than_since"
            msg = f"<b>Отзыв слишком старый.</b>\n<i>Нет отзывов, опубликованных после {since_naive:%d.%m.%Y}.</i>"
            self.__logger.info("Нет опубликованных отзывов с датой >= since для %s", email_norm)
            return {"ok": False, "reason": reason, "details": {"email": email, "since": since_naive.isoformat()},
                    "review": None, "html_message": msg}

        newer_or_equal = [(dt, r) for dt, r in with_dates if dt >= since_naive]
        if not newer_or_equal:
            latest_dt = max(dt for dt, _ in with_dates)
            reason = "only_older_than_since"
            msg = (
                f"<b>Отзыв найден, но слишком старый.</b>\n"
                f"<i>Последний отзыв был опубликован {latest_dt:%d.%m.%Y}, требуется не ранее {since_naive:%d.%m.%Y}.</i>"
            )
            self.__logger.info("Все отзывы старше since_dt для %s", email_norm)
            return {
                "ok": False,
                "reason": reason,
                "details": {"email": email, "since": since_naive.isoformat(), "latest_found": latest_dt.isoformat()},
                "review": None,
                "html_message": msg,
            }

        last_failure: Optional[Dict[str, Any]] = None
        for dt, r in sorted(newer_or_equal, key=lambda x: x[0], reverse=True):
            grade = int(r.get("grade", 0))
            text = (r.get("text") or "").strip()

            if grade < min_grade:
                reason = "low_grade"
                msg = (
                    f"<b>Оценка слишком низкая.</b>\n"
                    f"<i>Оценка {grade} ниже минимальной {min_grade}. "
                    f"Дата публикации {dt:%d.%m.%Y}.</i>"
                )
                self.__logger.debug("Review fails grade id=%s grade=%s required=%s", r.get("id"), grade, min_grade)
                last_failure = {
                    "ok": False, "reason": reason,
                    "details": {"email": email, "grade": grade, "required": min_grade, "pub_date": dt.isoformat()},
                    "review": r,
                    "html_message": msg
                }
                continue

            if len(text) < min_length:
                reason = "short_length"
                msg = (
                    f"<b>Текст отзыва слишком короткий.</b>\n"
                    f"<i>Длина {len(text)} символов, требуется минимум {min_length}. "
                    f"Дата публикации {dt:%d.%m.%Y}.</i>"
                )
                self.__logger.debug("Review fails length id=%s length=%s required=%s", r.get("id"), len(text),
                                    min_length)
                last_failure = {
                    "ok": False, "reason": reason,
                    "details": {"email": email, "length": len(text), "required": min_length,
                                "pub_date": dt.isoformat()},
                    "review": r,
                    "html_message": msg
                }
                continue

            # ✅ Passed all checks
            reason = "ok"
            msg = (
                f"<b>Отзыв успешно найден!</b>\n"
                f"<i>Опубликован {dt:%d.%m.%Y}, оценка {grade}, длина текста {len(text)} символов.</i>"
            )
            self.__logger.info("Найден корректный отзыв id=%s дата=%s оценка=%s", r.get("id"), dt, grade)
            return {
                "ok": True,
                "reason": reason,
                "details": {"email": email, "pub_date": dt.isoformat()},
                "review": r,
                "html_message": msg
            }

        # none passed full check
        if last_failure:
            self.__logger.info("Все найденные отзывы не прошли проверку. Последняя причина: %s", last_failure["reason"])
            return last_failure

        reason = "low_grade_or_short_length"
        msg = "<b>Отзыв найден, но не соответствует требованиям.</b>\n<i>Проверьте оценку и длину текста.</i>"
        self.__logger.info("Нет подходящих отзывов для %s — низкая оценка или короткий текст", email_norm)
        return {"ok": False, "reason": reason, "details": {"email": email}, "review": None, "html_message": msg}


client = AsyncElixirClient(MANAGER_USER, MANAGER_PASS)


# ---------------- example runner ----------------

async def main():
    if not await client.authorize():
        print("login failed")
        return

    verdict = await client.get_valid_review(
        email="sk_express.surgut@mail.ru",
        since_dt=datetime(2025, 9, 1, 0, 0, 0),
        min_grade=5,
        min_length=200,
    )
    print(verdict)

    # Save verdict for debugging (optional)
    async with aiofiles.open(os.path.join(DATA_DIR, "review_verdict.json"), "w", encoding="utf-8") as f:
        await f.write(json.dumps(verdict, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
