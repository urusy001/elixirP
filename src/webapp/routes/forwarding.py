import asyncio
import logging
import os
from typing import Optional

import httpx
from fastapi import Request, Header, Response, HTTPException, APIRouter

from src.helpers import verify_signature

logger = logging.getLogger("uvicorn.error")

TARGET_URL = "https://elixirpeptide.com/bitrix/tools/mibok.pay/sale_ps_result.php"
YOOKASSA_SECRET = os.getenv("YOOKASSA_SECRET")

FORWARD_TIMEOUT = 10.0
MAX_RETRIES = 2
RETRY_BACKOFF = 0.5
router = APIRouter()


@router.api_route("/yookassa-webhook", methods=["GET", "POST", "PUT", "HEAD", "OPTIONS"])
async def yookassa_forward(request: Request, x_yookassa_signature: Optional[str] = Header(None)):
    raw_body = await request.body()

    try:
        ok = await verify_signature(raw_body, x_yookassa_signature)
    except Exception as e:
        logger.exception("Signature verification failed: %s", e)
        raise HTTPException(status_code=500, detail="internal error")

    if not ok:
        logger.warning("Invalid signature on incoming webhook")
        raise HTTPException(status_code=403, detail="invalid signature")

    method = request.method
    headers = dict(request.headers)

    for hop in [
        "host", "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
        "te", "trailers", "transfer-encoding", "upgrade"
    ]:
        headers.pop(hop, None)

    headers.pop("authorization", None)
    headers["X-Forwarded-By"] = "my-fastapi-proxy"
    headers["X-Forwarded-For"] = request.client.host if request.client else "unknown"

    url = httpx.URL(TARGET_URL).copy_with(params=request.query_params)

    timeout = httpx.Timeout(FORWARD_TIMEOUT)
    async with httpx.AsyncClient(timeout=timeout, verify=True) as client:
        last_exc = None
        for attempt in range(1, MAX_RETRIES + 2):
            try:
                resp = await client.request(
                    method,
                    url,
                    content=raw_body if raw_body else None,
                    headers=headers,
                )
                logger.info(
                    "Forwarded %s %s -> %s : status=%d",
                    method, request.url.path, str(url), resp.status_code
                )
                if 200 <= resp.status_code < 300:
                    return Response(status_code=200)
                else:
                    logger.warning("Bitrix returned non-2xx: %d", resp.status_code)
                    return Response(status_code=500, content="forward_failed")
            except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                last_exc = exc
                logger.exception("Forward attempt %d failed: %s", attempt, exc)
                if attempt <= MAX_RETRIES:
                    await asyncio.sleep(RETRY_BACKOFF * attempt)
                    continue
                else:
                    break

    logger.error("Failed to forward webhook after retries: %s", last_exc)
    raise HTTPException(status_code=502, detail="failed to forward webhook")
