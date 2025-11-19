import logging
import asyncio
import signal
import sys

from config import TELETHON_PASSWORD, TELETHON_PHONE
from src.delivery.sdek import client as cdek_client
from src.tg_methods import client as tg_client
from src.onec import OneCEnterprise
from src.giveaway.bot.main import run_bot as run_giveaway_bot
from src.ai.bot.main import run_professor_bot, run_dose_bot, run_new_bot
from src.webapp.main import run_app
from src.webapp.database import init_db


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
logger = logging.getLogger("main")


async def main():
    await init_db(False)
    await tg_client.start(TELETHON_PHONE, TELETHON_PASSWORD or None)
    # Track all created tasks
    tasks = [
        asyncio.create_task(run_giveaway_bot()),
        asyncio.create_task(run_professor_bot()),
        asyncio.create_task(run_dose_bot()),
        asyncio.create_task(run_new_bot()),
        asyncio.create_task(OneCEnterprise().postgre_worker()),
        asyncio.create_task(cdek_client.token_worker()),
        asyncio.create_task(run_app()),
        asyncio.create_task(tg_client.start()),
    ]

    # Helper to cancel everything cleanly
    async def shutdown():
        logger.warning("🛑 Shutting down gracefully...")
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("✅ All background tasks stopped cleanly.")
        sys.exit(0)

    # Signal handlers for graceful exit
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(shutdown()))

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        logger.info("Tasks cancelled — exiting gracefully.")
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        await shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("Interrupted manually (Ctrl+C). Exiting.")
