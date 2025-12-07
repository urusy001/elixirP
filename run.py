import logging
import asyncio
import signal

from src.onec import OneCEnterprise
from src.admin_panel.bot.main import run_admin_bot
from src.delivery.sdek import client as cdek_client
from src.webapp.main import run_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
logger = logging.getLogger("main")


async def main():
    tasks = [
        asyncio.create_task(run_app()),
        asyncio.create_task(run_admin_bot()),
        asyncio.create_task(cdek_client()),
        asyncio.create_task(OneCEnterprise().postgres_worker())
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
