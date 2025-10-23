import logging
import asyncio

from src.giveaway.bot.main import run_bot as run_giveaway_bot

logging.basicConfig(
    level=logging.INFO,  # or INFO, WARNING, ERROR
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)  # only warnings/errors
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)    # pool logs

async def main():
    await run_giveaway_bot()


if __name__ == '__main__':
    logger = logging.getLogger()
    asyncio.run(main())
