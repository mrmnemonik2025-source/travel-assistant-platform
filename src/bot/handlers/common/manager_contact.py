import logging
from html import escape

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.formatting import Bold, Code, Text

from src.bot.config.settings import load_settings
from src.bot.keyboards.inline import ABOUT_CONTACT_MANAGER_CALLBACK
from src.bot.keyboards.reply import (
	CANCEL_MANAGER_MESSAGE_TEXT,
	main_menu_keyboard,
	manager_contact_keyboard,
)
from src.bot.states.manager_contact import ManagerContactStates


router = Router(name="common_manager_contact")
logger = logging.getLogger(__name__)


def build_contact_intro_text() -> str:
	return Text(
		"💬 ",
		Bold("Связь с менеджером"),
		"\n\n",
		"Напишите ваш вопрос одним сообщением.\n",
		"Менеджер получит его вместе с вашими Telegram-данными.",
	).as_html()


def build_manager_forward_text(message: Message, text: str) -> str:
	full_name = (message.from_user.full_name if message.from_user else "Не указано").strip() or "Не указано"
	username = f"@{message.from_user.username}" if message.from_user and message.from_user.username else "не указан"
	user_id = message.from_user.id if message.from_user else message.chat.id

	return Text(
		"🆕 ",
		Bold("Обращение к менеджеру"),
		"\n\n",
		"👤 ",
		Bold("Имя"),
		"\n",
		escape(full_name),
		"\n\n",
		"🔖 ",
		Bold("Username"),
		"\n",
		escape(username),
		"\n\n",
		"🆔 ",
		Bold("User ID"),
		"\n",
		Code(str(user_id)),
		"\n\n",
		"💬 ",
		Bold("Текст обращения"),
		"\n",
		escape(text),
	).as_html()


async def start_manager_contact(message: Message, state: FSMContext) -> None:
	settings = load_settings()
	if settings.manager_chat_id is None:
		logger.warning("MANAGER_CHAT_ID is not set, manager contact is unavailable")
		await message.answer(
			"Связь с менеджером временно недоступна. Попробуйте позже.",
			reply_markup=main_menu_keyboard,
		)
		return

	await state.clear()
	await state.set_state(ManagerContactStates.waiting_for_manager_message)
	await message.answer(
		build_contact_intro_text(),
		parse_mode=ParseMode.HTML,
		reply_markup=manager_contact_keyboard,
	)


@router.message(F.text == "💬 Связаться с менеджером")
async def start_manager_contact_from_menu(message: Message, state: FSMContext) -> None:
	await start_manager_contact(message, state)


@router.callback_query(F.data == ABOUT_CONTACT_MANAGER_CALLBACK)
async def start_manager_contact_from_inline(callback: CallbackQuery, state: FSMContext) -> None:
	if callback.message:
		await start_manager_contact(callback.message, state)
	await callback.answer()


@router.message(ManagerContactStates.waiting_for_manager_message, F.text == CANCEL_MANAGER_MESSAGE_TEXT)
async def cancel_manager_contact(message: Message, state: FSMContext) -> None:
	await state.clear()
	await message.answer(
		"Сообщение менеджеру отменено. Вы вернулись в главное меню.",
		reply_markup=main_menu_keyboard,
	)


@router.message(ManagerContactStates.waiting_for_manager_message)
async def handle_manager_message(message: Message, state: FSMContext) -> None:
	text = (message.text or "").strip()
	if not text:
		await message.answer(
			"Отправьте вопрос текстовым сообщением одним сообщением.",
			reply_markup=manager_contact_keyboard,
		)
		return

	if text.startswith("/"):
		await message.answer(
			"Пожалуйста, отправьте вопрос обычным текстом без команды.",
			reply_markup=manager_contact_keyboard,
		)
		return

	settings = load_settings()
	if settings.manager_chat_id is None:
		logger.warning("MANAGER_CHAT_ID is not set while sending manager contact message")
		await state.clear()
		await message.answer(
			"Связь с менеджером временно недоступна. Попробуйте позже.",
			reply_markup=main_menu_keyboard,
		)
		return

	try:
		await message.bot.send_message(
			chat_id=settings.manager_chat_id,
			text=build_manager_forward_text(message, text),
			parse_mode=ParseMode.HTML,
		)
	except Exception:
		logger.exception("Failed to send manager contact message")
		await message.answer(
			"Не удалось отправить сообщение менеджеру. Попробуйте немного позже.",
			reply_markup=main_menu_keyboard,
		)
		await state.clear()
		return

	await state.clear()
	await message.answer(
		"✅ Сообщение отправлено менеджеру. Мы скоро с вами свяжемся.",
		reply_markup=main_menu_keyboard,
	)
