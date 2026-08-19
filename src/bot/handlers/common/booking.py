import logging
import os
import re
from datetime import date

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, ReplyKeyboardRemove
from aiogram.utils.formatting import Bold, Code, Text

from src.bot.config.settings import load_settings
from src.bot.handlers.common.manager_contact import MANAGER_REPLY_CALLBACK_PREFIX
from src.bot.keyboards.inline import (
	BOOKING_CALENDAR_CANCEL_CALLBACK,
	BOOKING_CALENDAR_IGNORE_CALLBACK,
	BOOKING_CALENDAR_PREFIX,
	booking_result_keyboard,
	build_booking_calendar_keyboard,
)
from src.bot.keyboards.reply import booking_cancel_keyboard, booking_phone_keyboard, main_menu_keyboard
from src.bot.states.booking import BookingStates
from src.bot.services.bookings import BookingSubmissionData, booking_service
from src.bot.services.excursions import excursion_service


router = Router(name="common_booking")
logger = logging.getLogger(__name__)
DEMO_DISPLAY_PHONE = "+7 (999) 123-45-67"
DEMO_PHONE_ENV_VAR = "TRAVELFLOW_DEMO_PHONE"

BOOKING_DATE_PROMPT_CHAT_ID_KEY = "booking_date_prompt_chat_id"
BOOKING_DATE_PROMPT_MESSAGE_ID_KEY = "booking_date_prompt_message_id"
BOOKING_CALENDAR_MONTH_KEY = "booking_calendar_month"

MONTH_NAME_TO_NUMBER = {
	"января": 1,
	"январь": 1,
	"февраля": 2,
	"февраль": 2,
	"марта": 3,
	"март": 3,
	"апреля": 4,
	"апрель": 4,
	"мая": 5,
	"май": 5,
	"июня": 6,
	"июнь": 6,
	"июля": 7,
	"июль": 7,
	"августа": 8,
	"август": 8,
	"сентября": 9,
	"сентябрь": 9,
	"октября": 10,
	"октябрь": 10,
	"ноября": 11,
	"ноябрь": 11,
	"декабря": 12,
	"декабрь": 12,
}

DATE_WITH_DOTS_PATTERN = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$")
DATE_WITH_MONTH_PATTERN = re.compile(r"^(\d{1,2})\s+([А-Яа-яЁё]+)(?:\s+(\d{4}))?$")
LEGACY_RUSSIAN_PHONE_RE = re.compile(r"^\+?7(\d{10})$")
UX_RUSSIAN_PHONE_RE = re.compile(r"^(?:\+?7|8)?(9\d{9})$")


def format_phone_display(raw: str) -> str:
	"""Format Russian mobile numbers for display; keep non-Russian numbers unchanged."""
	cleaned = raw.strip()
	match = LEGACY_RUSSIAN_PHONE_RE.match(cleaned)
	if match:
		d = match.group(1)
		return f"+7 {d[:3]} {d[3:6]} {d[6:8]} {d[8:10]}"
	return cleaned


def format_phone_for_display(raw: str) -> str:
	"""Compatibility alias for the newer presentation format used in the final UX."""
	cleaned = raw.strip()
	match = UX_RUSSIAN_PHONE_RE.match(cleaned)
	if match:
		d = match.group(1)
		return f"+7 ({d[:3]}) {d[3:6]}-{d[6:8]}-{d[8:10]}"
	return cleaned


def build_manager_reply_keyboard(*, client_id: int) -> InlineKeyboardMarkup:
	return InlineKeyboardMarkup(
		inline_keyboard=[
			[
				InlineKeyboardButton(
					text="💬 Ответить клиенту",
					callback_data=f"{MANAGER_REPLY_CALLBACK_PREFIX}{client_id}",
				),
			],
		]
	)


def is_demo_phone_enabled() -> bool:
	value = os.getenv(DEMO_PHONE_ENV_VAR, "").strip().lower()
	return value in {"1", "true", "yes", "on"}


def get_display_phone(raw_phone: str) -> str:
	if is_demo_phone_enabled():
		return DEMO_DISPLAY_PHONE
	return format_phone_for_display(raw_phone)


def build_start_booking_text() -> str:
	return Text(
		"Как вас зовут?",
	).as_html()


def build_finish_booking_text(
	*,
	booking_id: int,
	excursion: str,
	phone: str,
	date: str,
	people: int,
	manager_delayed: bool = False,
) -> str:
	status_line = "✅ Заявка успешно отправлена!" if not manager_delayed else "✅ Заявка сохранена!"
	manager_line = (
		"Наш менеджер свяжется с вами в ближайшее время, чтобы подтвердить детали поездки."
		if not manager_delayed
		else "Наш менеджер свяжется с вами позже, как только сможет."
	)
	phone_display = get_display_phone(phone)
	return Text(
		"✅ ",
		Bold(status_line[2:]),
		"\n\n",
		"🆔 ",
		Bold("Номер заявки"),
		": ",
		str(booking_id),
		"\n\n",
		"🏝 ",
		Bold("Экскурсия"),
		"\n",
		excursion,
		"\n\n",
		"📅 ",
		Bold("Дата"),
		"\n",
		date,
		"\n\n",
		"👥 ",
		Bold("Количество гостей"),
		"\n",
		str(people),
		"\n\n",
		"📱 ",
		Bold("Контакт для связи"),
		"\n",
		phone_display,
		"\n\n",
		manager_line,
		"\n\n",
		"Спасибо, что выбрали ",
		Bold("Asia Mix Travel"),
		" 🌴",
	).as_html()


def build_manager_booking_text(
	*,
	booking_id: int,
	excursion: str,
	name: str,
	phone: str,
	date: str,
	people: int,
	username: str | None,
	user_id: int,
) -> str:
	username_value = f"@{username}" if username else "не указан"
	phone_display = get_display_phone(phone)
	return Text(
		"🆕 ",
		Bold("Новая заявка"),
		"\n\n",
		"🆔 ",
		Bold("Заявка №"),
		str(booking_id),
		"\n\n",
		"🏝 ",
		Bold("Экскурсия"),
		"\n",
		excursion,
		"\n\n",
		"👤 ",
		Bold("Клиент"),
		"\n",
		name,
		"\n\n",
		"📱 ",
		Bold("Телефон"),
		"\n",
		phone_display,
		"\n\n",
		"📅 ",
		Bold("Дата"),
		"\n",
		date,
		"\n\n",
		"👥 ",
		Bold("Количество человек"),
		"\n",
		str(people),
		"\n\n",
		Bold("Telegram"),
		"\n",
		f"Username: {username_value}\n",
		"User ID: ",
		Code(str(user_id)),
	).as_html()


async def ask_for_name(message: Message) -> None:
	await message.answer(
		build_start_booking_text(),
		parse_mode=ParseMode.HTML,
		reply_markup=booking_cancel_keyboard,
	)


def build_booking_date_prompt_text() -> str:
	return Text(
		"📅 ",
		Bold("Выберите дату экскурсии"),
		"\n\n",
		"Нажмите дату в календаре или введите её вручную:\n",
		Code("25.07.2026"),
	).as_html()


def format_booking_date(selected_date: date) -> str:
	return selected_date.strftime("%d.%m.%Y")


def get_initial_calendar_month() -> date:
	return date.today().replace(day=1)


def parse_booking_date_input(text: str) -> date | None:
	value = text.strip().lower()
	today = date.today()

	match = DATE_WITH_DOTS_PATTERN.fullmatch(value)
	if match:
		day, month, year = (int(part) for part in match.groups())
		try:
			selected_date = date(year, month, day)
		except ValueError:
			return None
		if selected_date < today:
			return None
		return selected_date

	match = DATE_WITH_MONTH_PATTERN.fullmatch(value)
	if not match:
		return None

	day = int(match.group(1))
	month_name = match.group(2).lower()
	year_text = match.group(3)
	month = MONTH_NAME_TO_NUMBER.get(month_name)
	if month is None:
		return None

	year = int(year_text) if year_text else today.year
	try:
		selected_date = date(year, month, day)
	except ValueError:
		return None

	if year_text is None and selected_date < today:
		try:
			selected_date = date(year + 1, month, day)
		except ValueError:
			return None

	if selected_date < today:
		return None

	return selected_date


async def send_booking_date_prompt(message: Message, state: FSMContext, *, month: date | None = None) -> None:
	selected_month = (month or get_initial_calendar_month()).replace(day=1)
	sent_message = await message.answer(
		build_booking_date_prompt_text(),
		parse_mode=ParseMode.HTML,
		reply_markup=build_booking_calendar_keyboard(selected_month),
	)
	await state.update_data(
		**{
			BOOKING_DATE_PROMPT_CHAT_ID_KEY: sent_message.chat.id,
			BOOKING_DATE_PROMPT_MESSAGE_ID_KEY: sent_message.message_id,
			BOOKING_CALENDAR_MONTH_KEY: selected_month.strftime("%Y-%m"),
		}
	)


async def update_date_prompt_message(
	*,
	message: Message,
	selected_date: date,
	prompt_chat_id: int | None = None,
	prompt_message_id: int | None = None,
	prompt_message: Message | None = None,
) -> None:
	selected_date_text = format_booking_date(selected_date)
	new_text = Text(
		"📅 ",
		Bold("Дата выбрана"),
		"\n\n",
		selected_date_text,
	).as_html()

	try:
		if prompt_message is not None:
			await prompt_message.edit_text(new_text, parse_mode=ParseMode.HTML)
		elif prompt_chat_id is not None and prompt_message_id is not None:
			await message.bot.edit_message_text(
				chat_id=prompt_chat_id,
				message_id=prompt_message_id,
				text=new_text,
				parse_mode=ParseMode.HTML,
			)
	except TelegramBadRequest:
			logger.debug("Failed to update booking date prompt message", exc_info=True)


async def proceed_to_people_step(
	message: Message,
	state: FSMContext,
	selected_date: date,
	*,
	prompt_message: Message | None = None,
	prompt_chat_id: int | None = None,
	prompt_message_id: int | None = None,
) -> None:
	await state.update_data(date=format_booking_date(selected_date))
	await state.set_state(BookingStates.waiting_for_people)
	await update_date_prompt_message(
		message=message,
		selected_date=selected_date,
		prompt_chat_id=prompt_chat_id,
		prompt_message_id=prompt_message_id,
		prompt_message=prompt_message,
	)
	await message.answer("👥 Сколько человек планирует поездку?")


async def cancel_booking_flow(message: Message, state: FSMContext) -> None:
	stored_data = await state.get_data()
	prompt_chat_id = stored_data.get(BOOKING_DATE_PROMPT_CHAT_ID_KEY)
	prompt_message_id = stored_data.get(BOOKING_DATE_PROMPT_MESSAGE_ID_KEY)
	if prompt_chat_id is not None and prompt_message_id is not None:
		try:
			await message.bot.edit_message_reply_markup(
				chat_id=int(prompt_chat_id),
				message_id=int(prompt_message_id),
				reply_markup=None,
			)
		except TelegramBadRequest:
			logger.debug("Failed to clear booking calendar markup on cancel", exc_info=True)
	await state.clear()
	await message.answer(
		"Заявка отменена. Вы вернулись в главное меню.",
		reply_markup=main_menu_keyboard,
	)


def get_state_calendar_month(stored_data: dict[str, object]) -> date:
	month_value = stored_data.get(BOOKING_CALENDAR_MONTH_KEY)
	if isinstance(month_value, str) and month_value:
		try:
			return date.fromisoformat(f"{month_value}-01")
		except ValueError:
			logger.debug("Invalid stored booking calendar month: %s", month_value)
	return get_initial_calendar_month()


@router.message(F.text == "📝 Оставить заявку")
async def start_booking_from_menu(message: Message, state: FSMContext) -> None:
	await state.clear()
	excursions = await excursion_service.list_effective_excursions()
	if not excursions:
		await message.answer("Каталог временно недоступен. Попробуйте позже или свяжитесь с менеджером.")
		return
	keyboard = InlineKeyboardMarkup(
		inline_keyboard=[
			[InlineKeyboardButton(
				text=excursion.short_title,
				callback_data=f"booking_select:{excursion.id}",
			)]
			for excursion in excursions
		]
	)
	await state.set_state(BookingStates.waiting_for_excursion)
	await message.answer(
		Text("📝 ", Bold("Оформление заявки"), "\n\n", "Выберите экскурсию:").as_html(),
		parse_mode=ParseMode.HTML,
		reply_markup=keyboard,
	)


@router.callback_query(BookingStates.waiting_for_excursion, F.data.startswith("booking_select:"))
async def handle_excursion_selection(callback: CallbackQuery, state: FSMContext) -> None:
	excursion_id = (callback.data or "").split(":", 1)[1]
	excursion = await excursion_service.get_effective_excursion(excursion_id)
	if excursion is None or not excursion.is_active:
		await callback.answer("Экскурсия временно недоступна", show_alert=True)
		return
	await state.update_data(
		excursion_id=excursion.id,
		excursion=excursion.title,
		excursion_title=excursion.title,
	)
	await state.set_state(BookingStates.waiting_for_name)
	if callback.message:
		try:
			await callback.message.edit_reply_markup(reply_markup=None)
		except TelegramBadRequest:
			logger.debug("Failed to remove excursion selection keyboard", exc_info=True)
		await ask_for_name(callback.message)
	await callback.answer()


@router.callback_query(F.data.startswith("booking:"))
async def start_booking_from_card(
	callback: CallbackQuery,
	state: FSMContext,
) -> None:
	excursion_id = callback.data.split(":", 1)[1] if callback.data else ""
	excursion = await excursion_service.get_effective_excursion(excursion_id)
	if excursion is None or not excursion.is_active:
		await callback.answer("Экскурсия временно недоступна", show_alert=True)
		return

	await state.clear()
	await state.update_data(
		excursion_id=excursion.id,
		excursion=excursion.title,
		excursion_title=excursion.title,
	)
	await state.set_state(BookingStates.waiting_for_name)
	if callback.message:
		await ask_for_name(callback.message)
	await callback.answer()


@router.callback_query(F.data.startswith(f"{BOOKING_CALENDAR_PREFIX}:"))
async def handle_booking_calendar(callback: CallbackQuery, state: FSMContext) -> None:
	if callback.data == BOOKING_CALENDAR_IGNORE_CALLBACK:
		await callback.answer()
		return

	if callback.data == BOOKING_CALENDAR_CANCEL_CALLBACK:
		if callback.message:
			try:
				await callback.message.edit_reply_markup(reply_markup=None)
			except TelegramBadRequest:
				logger.debug("Failed to clear booking calendar keyboard on cancel", exc_info=True)
			await cancel_booking_flow(callback.message, state)
		await callback.answer()
		return

	if not callback.message:
		await callback.answer("Календарь устарел.", show_alert=True)
		return

	parts = (callback.data or "").split(":", 2)
	if len(parts) != 3:
		await callback.answer("Календарь устарел.", show_alert=True)
		return

	action, value = parts[1], parts[2]
	today = date.today()
	current_month = today.replace(day=1)
	max_month = date(today.year + ((today.month - 1 + 12) // 12), ((today.month - 1 + 12) % 12) + 1, 1)

	if action == "month":
		try:
			year_str, month_str = value.split("-", 1)
			selected_month = date(int(year_str), int(month_str), 1)
		except ValueError:
			await callback.answer("Календарь устарел.", show_alert=True)
			return

		if selected_month < current_month or selected_month > max_month:
			await callback.answer("Календарь устарел.", show_alert=True)
			return

		await state.update_data(**{BOOKING_CALENDAR_MONTH_KEY: selected_month.strftime("%Y-%m")})
		try:
			await callback.message.edit_reply_markup(
				reply_markup=build_booking_calendar_keyboard(selected_month),
			)
		except TelegramBadRequest:
			logger.debug("Failed to update booking calendar month", exc_info=True)
		await callback.answer()
		return

	if action == "day":
		try:
			year_str, month_str, day_str = value.split("-", 2)
			selected_date = date(int(year_str), int(month_str), int(day_str))
		except ValueError:
			await callback.answer("Календарь устарел.", show_alert=True)
			return

		if selected_date < today:
			await callback.answer("Эта дата уже прошла.", show_alert=True)
			return

		await proceed_to_people_step(message=callback.message, state=state, selected_date=selected_date, prompt_message=callback.message)
		await callback.answer()
		return

	await callback.answer("Календарь устарел.", show_alert=True)


@router.message(StateFilter(BookingStates), F.text == "❌ Отменить заявку")
async def cancel_booking_in_state(message: Message, state: FSMContext) -> None:
	await cancel_booking_flow(message, state)


@router.message(BookingStates.waiting_for_excursion)
async def handle_excursion_state_text(message: Message) -> None:
	await message.answer("Пожалуйста, выберите экскурсию из списка выше.")


@router.message(BookingStates.waiting_for_name)
async def handle_name(message: Message, state: FSMContext) -> None:
	name = (message.text or "").strip()
	if not name:
		await message.answer("Пожалуйста, введите имя.")
		return

	await state.update_data(name=name)
	await state.set_state(BookingStates.waiting_for_phone)
	await message.answer(
		"📱 Укажите номер телефона.\n\n"
		"Вы можете отправить контакт кнопкой ниже или ввести номер вручную.\n"
		"Формат: +7 (928) 234-25-03",
		reply_markup=booking_phone_keyboard,
	)


@router.message(BookingStates.waiting_for_phone, F.contact)
async def handle_phone_contact(message: Message, state: FSMContext) -> None:
	phone = (message.contact.phone_number or "").strip()
	await state.update_data(phone=phone)
	await state.set_state(BookingStates.waiting_for_date)
	await message.answer("✅ Контакт получен.", reply_markup=ReplyKeyboardRemove())
	await send_booking_date_prompt(message, state)


@router.message(BookingStates.waiting_for_phone)
async def handle_phone_text(message: Message, state: FSMContext) -> None:
	phone = (message.text or "").strip()
	if not phone:
		await message.answer("Пожалуйста, укажите номер телефона.")
		return

	await state.update_data(phone=phone)
	await state.set_state(BookingStates.waiting_for_date)
	await message.answer("✅ Телефон принят.", reply_markup=ReplyKeyboardRemove())
	await send_booking_date_prompt(message, state)


@router.message(BookingStates.waiting_for_date)
async def handle_date(message: Message, state: FSMContext) -> None:
	trip_date = (message.text or "").strip()
	if not trip_date:
		await message.answer("Пожалуйста, укажите корректную дату экскурсии.")
		stored_data = await state.get_data()
		await send_booking_date_prompt(
			message,
			state,
			month=get_state_calendar_month(stored_data),
		)
		return

	parsed_date = parse_booking_date_input(trip_date)
	if parsed_date is None:
		await message.answer(
			"Пожалуйста, укажите корректную дату. Например: 25.07.2026",
		)
		stored_data = await state.get_data()
		await send_booking_date_prompt(message, state, month=get_state_calendar_month(stored_data))
		return

	stored_data = await state.get_data()
	prompt_chat_id = stored_data.get(BOOKING_DATE_PROMPT_CHAT_ID_KEY)
	prompt_message_id = stored_data.get(BOOKING_DATE_PROMPT_MESSAGE_ID_KEY)
	await proceed_to_people_step(
		message=message,
		state=state,
		selected_date=parsed_date,
		prompt_chat_id=int(prompt_chat_id) if prompt_chat_id is not None else None,
		prompt_message_id=int(prompt_message_id) if prompt_message_id is not None else None,
	)


@router.message(BookingStates.waiting_for_people)
async def handle_people(message: Message, state: FSMContext) -> None:
	people_text = (message.text or "").strip()
	if not people_text.isdigit():
		await message.answer("Введите целое число от 1 до 50.")
		return

	people = int(people_text)
	if people < 1 or people > 50:
		await message.answer("Введите целое число от 1 до 50.")
		return

	data = await state.get_data()
	excursion_id = str(data.get("excursion_id", "not_selected") or "not_selected")
	excursion_title = str(data.get("excursion_title", data.get("excursion", "Не выбрана")) or "Не выбрана")
	excursion = data.get("excursion", "Не выбрана")
	name = data.get("name", "")
	phone = data.get("phone", "")
	date = data.get("date", "")
	username = message.from_user.username if message.from_user else None
	user_id = message.from_user.id if message.from_user else message.chat.id
	full_name = message.from_user.full_name if message.from_user else None
	full_name = full_name if full_name else None

	try:
		booking_id = await booking_service.save_booking(
			BookingSubmissionData(
				excursion_id=excursion_id,
				excursion_title=excursion_title,
				customer_name=name,
				phone=phone,
				excursion_date=date,
				people_count=people,
				telegram_user_id=user_id,
				telegram_username=username,
				telegram_full_name=full_name,
			)
		)
	except Exception:
		logger.exception("Failed to save booking to SQLite")
		await message.answer(
			"Не удалось сохранить заявку. Попробуйте ещё раз или свяжитесь с менеджером.",
		)
		return

	await state.update_data(people=people)

	settings = load_settings()
	manager_sent = False
	if settings.manager_chat_id is None:
		logger.warning("MANAGER_CHAT_ID is not set, manager notification skipped")
	else:
		try:
			await message.bot.send_message(
				chat_id=settings.manager_chat_id,
				text=build_manager_booking_text(
					booking_id=booking_id,
					excursion=excursion,
					name=name,
					phone=phone,
					date=date,
					people=people,
					username=username,
					user_id=user_id,
				),
				parse_mode=ParseMode.HTML,
				reply_markup=build_manager_reply_keyboard(client_id=user_id),
			)
			manager_sent = True
		except Exception:
			logger.exception("Failed to send booking notification to manager")

	await state.clear()

	await message.answer(
		build_finish_booking_text(
			booking_id=booking_id,
			excursion=excursion,
			phone=phone,
			date=date,
			people=people,
			manager_delayed=not manager_sent,
		),
		parse_mode=ParseMode.HTML,
		reply_markup=booking_result_keyboard,
	)

	await message.answer(
		"🏠 Главное меню",
		reply_markup=main_menu_keyboard,
	)