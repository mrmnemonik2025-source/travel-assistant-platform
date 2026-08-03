import logging

from aiogram.types import CallbackQuery, Message

from src.bot.config.settings import load_settings


logger = logging.getLogger(__name__)


def is_admin_user_id(user_id: int | None) -> bool:
	if user_id is None:
		return False
	settings = load_settings()
	if not settings.admin_user_ids:
		return False
	return user_id in settings.admin_user_ids


async def ensure_admin_message_access(message: Message, *, action: str) -> bool:
	user_id = message.from_user.id if message.from_user else None
	if is_admin_user_id(user_id):
		return True

	logger.warning("Admin access denied: action=%s user_id=%s", action, user_id)
	await message.answer("Доступ запрещён.")
	return False


async def ensure_admin_callback_access(callback: CallbackQuery, *, action: str) -> bool:
	user_id = callback.from_user.id if callback.from_user else None
	if is_admin_user_id(user_id):
		return True

	logger.warning("Admin access denied: action=%s user_id=%s", action, user_id)
	await callback.answer("Доступ запрещён.", show_alert=True)
	return False