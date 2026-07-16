from dataclasses import dataclass
import os


@dataclass(slots=True)
class Settings:
	bot_token: str
	log_level: str = "INFO"


def load_settings() -> Settings:
	bot_token = os.getenv("BOT_TOKEN")
	if not bot_token:
		raise RuntimeError("Environment variable BOT_TOKEN is required")

	return Settings(
		bot_token=bot_token,
		log_level=os.getenv("LOG_LEVEL", "INFO"),
	)
