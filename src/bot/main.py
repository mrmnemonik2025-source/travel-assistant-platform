import asyncio
import logging

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

from src.bot.config.settings import load_settings


def setup_logging(log_level: str) -> None:
	logging.basicConfig(
		level=getattr(logging, log_level.upper(), logging.INFO),
		format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
	)


async def main() -> None:
	load_dotenv()
	settings = load_settings()
	setup_logging(settings.log_level)

	logger = logging.getLogger(__name__)
	logger.info("Starting bot")

	bot = Bot(token=settings.bot_token)
	dispatcher = Dispatcher()

	try:
		await dispatcher.start_polling(bot)
	finally:
		await bot.session.close()


if __name__ == "__main__":
	asyncio.run(main())
