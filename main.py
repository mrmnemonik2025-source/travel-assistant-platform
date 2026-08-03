import asyncio
import os

import uvicorn

from src.bot.main import main as bot_main
from src.web.app import app


async def main() -> None:
	server = uvicorn.Server(
		uvicorn.Config(
			app,
			host="0.0.0.0",
			port=int(os.getenv("PORT", "8000")),
			log_level=os.getenv("LOG_LEVEL", "info").lower(),
		)
	)
	bot_task = asyncio.create_task(bot_main(), name="telegram-bot")
	web_task = asyncio.create_task(server.serve(), name="web-platform")
	tasks = {bot_task, web_task}

	done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
	for task in done:
		if not task.cancelled() and task.exception() is not None:
			for pending_task in pending:
				pending_task.cancel()
			await asyncio.gather(*pending, return_exceptions=True)
			raise task.exception()

	for pending_task in pending:
		pending_task.cancel()
	await asyncio.gather(*pending, return_exceptions=True)


if __name__ == "__main__":
	asyncio.run(main())
