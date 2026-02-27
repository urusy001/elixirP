import logging
import asyncio
import signal

from src.ai.bot.main import run_new_bot, run_dose_bot, run_professor_bot
from src.logger import setup_logging
from src.tg_methods import client as tg_client

logger = logging.getLogger("main")


async def main():
    await tg_client.start()
    tasks = [
        asyncio.create_task(run_new_bot()),
        asyncio.create_task(run_dose_bot()),
        asyncio.create_task(run_professor_bot()),
    ]

    async def shutdown():
        logger.warning("🛑 Shutting down gracefully...")
        [task.cancel() for task in tasks if not task.done()]
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("✅ All background tasks stopped cleanly.")

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM): loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(shutdown()))

    try: await asyncio.gather(*tasks)
    except asyncio.CancelledError: logger.info("Tasks cancelled — exiting gracefully.")
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        await shutdown()


if __name__ == "__main__":
    setup_logging()
    try: asyncio.run(main())
    except KeyboardInterrupt: logger.warning("Interrupted manually (Ctrl+C). Exiting.")
