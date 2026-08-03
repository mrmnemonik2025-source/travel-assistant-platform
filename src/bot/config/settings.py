from dataclasses import dataclass
import os


@dataclass(slots=True)
class Settings:
	bot_token: str
	log_level: str = "INFO"
	manager_chat_id: int | None = None
	admin_user_ids: frozenset[int] = frozenset()


def parse_admin_user_ids(raw_value: str) -> frozenset[int]:
	value = raw_value.strip()
	if not value:
		return frozenset()

	user_ids: set[int] = set()
	for part in value.split(","):
		cleaned = part.strip()
		if not cleaned:
			continue
		try:
			user_id = int(cleaned)
		except ValueError as error:
			raise RuntimeError("Environment variable ADMIN_USER_IDS must contain integers separated by commas") from error
		if user_id <= 0:
			raise RuntimeError("Environment variable ADMIN_USER_IDS must contain only positive integers")
		user_ids.add(user_id)

	return frozenset(user_ids)


def load_settings() -> Settings:
	bot_token = os.getenv("BOT_TOKEN")
	if not bot_token:
		raise RuntimeError("Environment variable BOT_TOKEN is required")

	manager_chat_id_raw = os.getenv("MANAGER_CHAT_ID", "").strip()
	try:
		manager_chat_id = int(manager_chat_id_raw) if manager_chat_id_raw else None
	except ValueError as error:
		raise RuntimeError("Environment variable MANAGER_CHAT_ID must be an integer") from error
	if manager_chat_id == 0:
		raise RuntimeError("Environment variable MANAGER_CHAT_ID must not be zero")
	admin_user_ids = parse_admin_user_ids(os.getenv("ADMIN_USER_IDS", ""))

	return Settings(
		bot_token=bot_token,
		log_level=os.getenv("LOG_LEVEL", "INFO"),
		manager_chat_id=manager_chat_id,
		admin_user_ids=admin_user_ids,
	)
