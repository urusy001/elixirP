import logging
import asyncio
import signal

from config import TELETHON_PHONE, TELETHON_PASSWORD
from src.ai.bot.main import run_dose_bot, run_professor_bot
from src.antispam.bot.main import run_antispam_bot
from src.giveaway.bot.main import run_bot
from src.tg_methods import client as telegram_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
logger = logging.getLogger("main")


async def main():
    await telegram_client.start(TELETHON_PHONE, TELETHON_PASSWORD)
    tasks = [
        asyncio.create_task(run_antispam_bot()),
        asyncio.create_task(run_dose_bot()),
        asyncio.create_task(run_professor_bot()),
        asyncio.create_task(run_bot()),
    ]

    async def shutdown():
        logger.warning("🛑 Shutting down gracefully...")
        for task in tasks:
            if not task.done(): task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("✅ All background tasks stopped cleanly.")

    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(shutdown()))

    try: await asyncio.gather(*tasks)
    except asyncio.CancelledError: logger.info("Tasks cancelled — exiting gracefully.")
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        await shutdown()


if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: logger.warning("Interrupted manually (Ctrl+C). Exiting.")
