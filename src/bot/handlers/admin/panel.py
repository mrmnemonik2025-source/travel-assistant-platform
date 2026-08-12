import logging
import os
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from tempfile import NamedTemporaryFile
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, Message
from aiogram.utils.formatting import Bold, Code, Text

from src.bot.handlers.admin.access import ensure_admin_callback_access, ensure_admin_message_access
from src.bot.handlers.common.catalog import build_excursion_content, resolve_excursion_image_path
from src.bot.keyboards.inline import (
	build_admin_excursion_card_keyboard,
	build_admin_excursion_hide_confirm_keyboard,
	build_admin_excursion_list_keyboard,
	build_admin_excursion_photo_keyboard,
	build_admin_excursion_photo_reset_confirm_keyboard,
	build_admin_excursion_preview_keyboard,
	build_admin_excursion_reset_confirm_keyboard,
	build_admin_booking_card_keyboard,
	build_admin_booking_list_keyboard,
	build_admin_menu_keyboard,
	build_admin_search_cancel_keyboard,
	build_admin_search_no_results_keyboard,
	build_admin_status_filters_keyboard,
)
from src.bot.keyboards.reply import (
	CANCEL_ADMIN_EXCURSION_EDIT_TEXT,
	CANCEL_ADMIN_EXCURSION_PHOTO_UPLOAD_TEXT,
	admin_excursion_edit_cancel_keyboard,
	admin_excursion_photo_cancel_keyboard,
	main_menu_keyboard,
)
from src.bot.repositories.bookings import BookingRow
from src.bot.services.bookings import booking_service
from src.bot.services.excursions import excursion_service
from src.bot.states.admin import AdminExcursionEditStates, AdminSearchStates


router = Router(name="admin_panel")
logger = logging.getLogger(__name__)

BOOKINGS_PER_PAGE = 5

ADMIN_SOURCE_NEW = "new"
ADMIN_SOURCE_ALL = "all"
ADMIN_SOURCE_STATUS_NEW = "status_new"
ADMIN_SOURCE_STATUS_IN_PROGRESS = "status_in_progress"
ADMIN_SOURCE_STATUS_CONFIRMED = "status_confirmed"
ADMIN_SOURCE_STATUS_COMPLETED = "status_completed"
ADMIN_SOURCE_STATUS_CANCELLED = "status_cancelled"

VALID_SOURCES = {
	ADMIN_SOURCE_NEW,
	ADMIN_SOURCE_ALL,
	ADMIN_SOURCE_STATUS_NEW,
	ADMIN_SOURCE_STATUS_IN_PROGRESS,
	ADMIN_SOURCE_STATUS_CONFIRMED,
	ADMIN_SOURCE_STATUS_COMPLETED,
	ADMIN_SOURCE_STATUS_CANCELLED,
}

MAX_EXCURSION_IMAGE_BYTES = 10 * 1024 * 1024
ALLOWED_TELEGRAM_IMAGE_EXTENSIONS: set[str] = {".jpg", ".jpeg", ".png", ".webp"}

BOOKING_STATUSES: dict[str, str] = {
	"new": "Новая",
	"in_progress": "В работе",
	"confirmed": "Подтверждена",
	"completed": "Завершена",
	"cancelled": "Отменена",
}

EXCURSION_EDITABLE_FIELDS: set[str] = {"title", "short_title", "time", "price", "description", "included"}
EXCURSION_EDIT_FIELD_LABELS: dict[str, str] = {
	"title": "Название",
	"short_title": "Короткое название",
	"time": "Время",
	"price": "Цена",
	"description": "Описание",
	"included": "Что включено",
}

EXCURSION_FIELD_LIMITS: dict[str, tuple[int, int]] = {
	"title": (2, 120),
	"short_title": (2, 64),
	"time": (1, 100),
	"price": (1, 100),
	"description": (1, 1500),
	"included": (1, 1500),
}


def build_admin_excursion_photo_status_text(source: str) -> str:
	if source == "override":
		return "Сейчас используется загруженная администратором фотография."
	if source == "base":
		return "Сейчас используется исходная фотография экскурсии."
	return "Сейчас используется placeholder-фотография."


def build_admin_excursion_photo_screen_text(source: str) -> str:
	return Text(
		"🖼 ",
		Bold("Фотография экскурсии"),
		"\n\n",
		build_admin_excursion_photo_status_text(source),
		"\n\n",
		"Отправьте новую фотографию одним сообщением.",
		"\n\n",
		"После загрузки она будет использоваться в каталоге и предпросмотре.",
	).as_html()


def _guess_image_extension(file_path: str | None) -> str:
	if not file_path:
		return ".jpg"
	return Path(file_path).suffix.lower() or ".jpg"


def build_admin_menu_text() -> str:
	return Text(
		"🛠 ",
		Bold("Панель администратора"),
		"\n\n",
		"Выберите раздел:",
	).as_html()


def build_status_filters_text() -> str:
	return Text(
		"📂 ",
		Bold("Заявки по статусу"),
	).as_html()


def build_search_prompt_text() -> str:
	return Text(
		"🔎 ",
		Bold("Поиск заявки"),
		"\n\n",
		"Введите:\n",
		"• номер заявки;\n",
		"• имя клиента;\n",
		"• телефон;\n",
		"• Telegram username.",
	).as_html()


def build_admin_excursions_list_text() -> str:
	return Text(
		"🏝 ",
		Bold("Управление экскурсиями"),
		"\n\n",
		"Выберите экскурсию для просмотра и редактирования:",
	).as_html()


def build_admin_bookings_list_text(*, source: str, page: int, total_pages: int) -> str:
	return Text(
		"📋 ",
		Bold("Управление заявками"),
		"\n\n",
		Bold("Раздел:"),
		" ",
		escape(get_source_title(source)),
		"\n",
		f"Страница {page} из {total_pages}",
		"\n\n",
		"Выберите заявку:",
	).as_html()


def _is_missing_value(value: str | None) -> bool:
	if value is None:
		return True
	clean = value.strip()
	if not clean:
		return True
	return "TODO" in clean.upper()


def _truncate_multiline(value: str, *, limit: int) -> tuple[str, bool]:
	clean = value.strip()
	if len(clean) <= limit:
		return clean, False
	return f"{clean[:limit].rstrip()}...", True


def _escape_or_placeholder(value: str | None, *, placeholder: str) -> str:
	if _is_missing_value(value):
		return placeholder
	return escape((value or "").strip())


def _format_included_value(included: tuple[str, ...]) -> str:
	lines = [line.strip() for line in included if line and not _is_missing_value(line)]
	if not lines:
		return "Не указано"
	joined = "\n".join(lines)
	short, was_truncated = _truncate_multiline(joined, limit=700)
	escaped = escape(short)
	if was_truncated:
		return f"{escaped}\n\n<i>Показан сокращенный фрагмент. Полный текст доступен в режиме редактирования.</i>"
	return escaped


def build_admin_excursion_card_text(
	*,
	excursion_title: str,
	time: str,
	price: str,
	description: str,
	included: tuple[str, ...],
	is_active: bool,
) -> str:
	status = "Активна" if is_active else "Скрыта"
	time_value = _escape_or_placeholder(time, placeholder="Не указано")
	price_value = _escape_or_placeholder(price, placeholder="Не указана")
	description_source = "" if _is_missing_value(description) else description.strip()
	description_preview = "Не указано"
	if description_source:
		short, was_truncated = _truncate_multiline(description_source, limit=700)
		description_preview = escape(short)
		if was_truncated:
			description_preview = (
				f"{description_preview}\n\n"
				"<i>Показан сокращенный фрагмент. Полный текст доступен в режиме редактирования.</i>"
			)
	included_text = _format_included_value(included)

	return Text(
		"🏝 ",
		Bold(escape(excursion_title)),
		"\n\n",
		"📌 ",
		Bold("Статус:"),
		" ",
		status,
		"\n",
		"🕒 ",
		Bold("Время:"),
		" ",
		time_value,
		"\n",
		"💰 ",
		Bold("Цена:"),
		" ",
		price_value,
		"\n\n",
		"📝 ",
		Bold("Описание:"),
		"\n",
		description_preview,
		"\n\n",
		"✅ ",
		Bold("Что включено:"),
		"\n",
		included_text,
	).as_html()


def validate_excursion_field_value(field_name: str, value: str) -> str | None:
	clean = "\n".join(line.rstrip() for line in value.strip().splitlines()).strip()
	if not clean:
		return "Поле не может быть пустым или состоять только из пробелов."

	if clean.startswith("/"):
		return "Команды вида /admin или /start нельзя сохранять как значение поля."

	limits = EXCURSION_FIELD_LIMITS.get(field_name)
	if limits is None:
		return "Неизвестное поле для редактирования."

	min_len, max_len = limits
	length = len(clean)
	if length < min_len or length > max_len:
		return (
			f"Недопустимая длина для поля '{EXCURSION_EDIT_FIELD_LABELS[field_name]}'. "
			f"Разрешено: {min_len}-{max_len} символов."
		)

	if field_name == "included":
		items = [line.strip("-• \t") for line in clean.splitlines() if line.strip()]
		if not items:
			return "Поле 'Что включено' должно содержать хотя бы один непустой пункт."

	if field_name == "short_title" and len(clean) > 64:
		return "Для поля 'Короткое название' допустимо максимум 64 символа."

	if field_name in {"time", "price"} and len(clean) > 100:
		return f"Для поля '{EXCURSION_EDIT_FIELD_LABELS[field_name]}' допустимо максимум 100 символов."

	return None


def build_excursion_field_constraints(field_name: str) -> str:
	min_len, max_len = EXCURSION_FIELD_LIMITS[field_name]
	return f"Ограничение: {min_len}-{max_len} символов."


def normalize_excursion_field_value(field_name: str, value: str) -> str:
	clean = "\n".join(line.rstrip() for line in value.strip().splitlines()).strip()
	if field_name != "included":
		return clean
	items = [line.strip("-• \t") for line in clean.splitlines() if line.strip()]
	return "\n".join(items)


def get_excursion_field_current_value(excursion_id: str, field_name: str, excursion: object) -> str:
	if field_name == "title":
		value = getattr(excursion, "title", "")
	elif field_name == "short_title":
		value = getattr(excursion, "short_title", "")
	elif field_name == "time":
		value = getattr(excursion, "time", "")
	elif field_name == "price":
		value = getattr(excursion, "price", "")
	elif field_name == "description":
		value = getattr(excursion, "description", "")
	elif field_name == "included":
		included = getattr(excursion, "included", ())
		value = "\n".join(str(line).strip() for line in included if str(line).strip())
	else:
		raise ValueError(f"Unsupported field for excursion {excursion_id}: {field_name}")

	if _is_missing_value(value):
		return "Не указано"
	return str(value).strip()


def get_status_label(status: str) -> str:
	return BOOKING_STATUSES.get(status, "Неизвестно")


def get_source_status(source: str) -> str | None:
	mapping = {
		ADMIN_SOURCE_NEW: "new",
		ADMIN_SOURCE_ALL: None,
		ADMIN_SOURCE_STATUS_NEW: "new",
		ADMIN_SOURCE_STATUS_IN_PROGRESS: "in_progress",
		ADMIN_SOURCE_STATUS_CONFIRMED: "confirmed",
		ADMIN_SOURCE_STATUS_COMPLETED: "completed",
		ADMIN_SOURCE_STATUS_CANCELLED: "cancelled",
	}
	return mapping.get(source)


def get_source_title(source: str) -> str:
	mapping = {
		ADMIN_SOURCE_NEW: "Новые заявки",
		ADMIN_SOURCE_ALL: "Все заявки",
		ADMIN_SOURCE_STATUS_NEW: "Заявки: Новые",
		ADMIN_SOURCE_STATUS_IN_PROGRESS: "Заявки: В работе",
		ADMIN_SOURCE_STATUS_CONFIRMED: "Заявки: Подтверждённые",
		ADMIN_SOURCE_STATUS_COMPLETED: "Заявки: Завершённые",
		ADMIN_SOURCE_STATUS_CANCELLED: "Заявки: Отменённые",
	}
	return mapping.get(source, "Заявки")


def sanitize_page(page_raw: str) -> int | None:
	if not page_raw.isdigit():
		return None
	page = int(page_raw)
	if page < 1:
		return None
	return page


def normalize_page(page: int, total_pages: int) -> int:
	if total_pages < 1:
		return 1
	if page < 1:
		return 1
	if page > total_pages:
		return total_pages
	return page


def compact_excursion_title(title: str, limit: int = 22) -> str:
	trimmed = " ".join(title.split())
	if len(trimmed) <= limit:
		return trimmed
	return f"{trimmed[: limit - 1]}…"


def format_booking_created_at(raw_value: str) -> str:
	try:
		created_at = datetime.fromisoformat(raw_value)
	except ValueError:
		return raw_value

	if created_at.tzinfo is None:
		created_at = created_at.replace(tzinfo=timezone.utc)

	local_dt = created_at.astimezone(ZoneInfo("Asia/Ho_Chi_Minh"))
	return local_dt.strftime("%d.%m.%Y в %H:%M")


def build_booking_card_text(*, booking: BookingRow) -> str:
	status_label = escape(get_status_label(booking.status))
	excursion_title = escape(booking.excursion_title)
	customer_name = escape(booking.customer_name)
	phone = escape(booking.phone)
	excursion_date = escape(booking.excursion_date)
	created_at = escape(format_booking_created_at(booking.created_at))
	username_raw = booking.telegram_username
	username = f"@{username_raw}" if username_raw else "не указан"

	return Text(
		"🧾 ",
		Bold(f"Заявка №{booking.id}"),
		"\n\n",
		"📌 ",
		Bold("Статус:"),
		" ",
		status_label,
		"\n",
		"🏝 ",
		Bold("Экскурсия:"),
		" ",
		excursion_title,
		"\n",
		"👤 ",
		Bold("Клиент:"),
		" ",
		customer_name,
		"\n",
		"📱 ",
		Bold("Телефон:"),
		" ",
		phone,
		"\n",
		"📅 ",
		Bold("Дата:"),
		" ",
		excursion_date,
		"\n",
		"👥 ",
		Bold("Гостей:"),
		" ",
		str(booking.people_count),
		"\n",
		"🕒 ",
		Bold("Создана:"),
		" ",
		created_at,
		"\n\n",
		Bold("Telegram"),
		"\n",
		"Username: ",
		escape(username),
		"\n",
		"User ID: ",
		Code(str(booking.telegram_user_id)),
	).as_html()


def build_admin_stats_text(*, total: int, new: int, in_progress: int, confirmed: int, completed: int, cancelled: int) -> str:
	return Text(
		"📊 ",
		Bold("Статистика заявок"),
		"\n\n",
		"Всего заявок: ",
		str(total),
		"\n",
		"Новых: ",
		str(new),
		"\n",
		"В работе: ",
		str(in_progress),
		"\n",
		"Подтверждённых: ",
		str(confirmed),
		"\n",
		"Завершённых: ",
		str(completed),
		"\n",
		"Отменённых: ",
		str(cancelled),
	).as_html()


def build_no_results_keyboard(source: str) -> InlineKeyboardMarkup:
	buttons: list[list[InlineKeyboardButton]] = []
	if source.startswith("status_"):
		buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:filters:status")])
	else:
		buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:list:all:1")])
	buttons.append([InlineKeyboardButton(text="🛠 В админ-меню", callback_data="admin:menu")])
	return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_search_results_keyboard(rows: list[BookingRow]) -> InlineKeyboardMarkup:
	keyboard_rows: list[list[InlineKeyboardButton]] = []
	for row in rows:
		label = f"№{row.id} · {compact_excursion_title(row.excursion_title)} · {row.customer_name}"
		keyboard_rows.append(
			[
				InlineKeyboardButton(
					text=label[:64],
					callback_data=f"admin:search:booking:{row.id}",
				),
			]
		)
	keyboard_rows.append([InlineKeyboardButton(text="🛠 В админ-меню", callback_data="admin:menu")])
	return InlineKeyboardMarkup(inline_keyboard=keyboard_rows)


async def clear_admin_search_state(state: FSMContext) -> None:
	current_state = await state.get_state()
	if current_state and current_state.startswith("AdminSearchStates:"):
		await state.clear()


async def clear_admin_excursion_edit_state(state: FSMContext) -> None:
	current_state = await state.get_state()
	if current_state and current_state.startswith("AdminExcursionEditStates:"):
		await state.clear()


async def show_admin_menu_message(message: Message) -> None:
	await message.answer(
		build_admin_menu_text(),
		parse_mode=ParseMode.HTML,
		reply_markup=build_admin_menu_keyboard(),
	)


async def edit_or_send_admin_view(callback: CallbackQuery, *, text: str, reply_markup: object) -> None:
	if callback.message is None:
		await callback.answer("Действие недоступно.", show_alert=True)
		return

	try:
		await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
	except TelegramBadRequest:
		await callback.message.answer(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)


async def clear_inline_keyboard(message: Message | None) -> None:
	if message is None:
		return
	try:
		await message.edit_reply_markup(reply_markup=None)
	except TelegramBadRequest:
		logger.debug("Failed to clear stale inline keyboard", exc_info=True)


async def show_bookings_list(callback: CallbackQuery, *, source: str, requested_page: int) -> None:
	if source not in VALID_SOURCES:
		await callback.answer("Действие недоступно.", show_alert=True)
		return

	status_filter = get_source_status(source)
	total_items = await booking_service.count_bookings(status=status_filter)
	total_pages = max(1, (total_items + BOOKINGS_PER_PAGE - 1) // BOOKINGS_PER_PAGE)
	page = normalize_page(requested_page, total_pages)
	offset = (page - 1) * BOOKINGS_PER_PAGE
	rows = await booking_service.list_bookings(
		limit=BOOKINGS_PER_PAGE,
		offset=offset,
		status=status_filter,
		order_desc=True,
	)

	if rows:
		text = build_admin_bookings_list_text(source=source, page=page, total_pages=total_pages)
		keyboard_rows = [
			(
				row.id,
				row.status,
				compact_excursion_title(row.excursion_title),
				row.customer_name,
				row.excursion_date,
			)
			for row in rows
		]
		reply_markup = build_admin_booking_list_keyboard(
			rows=keyboard_rows,
			source=source,
			page=page,
			total_pages=total_pages,
		)
	else:
		text = Text(
			"📋 ",
			Bold("Управление заявками"),
			"\n\n",
			"Заявок не найдено.",
		).as_html()
		reply_markup = build_no_results_keyboard(source)

	await edit_or_send_admin_view(callback, text=text, reply_markup=reply_markup)
	await callback.answer()


async def show_booking_card(
	callback: CallbackQuery,
	*,
	booking_id: int,
	source: str,
	page: int,
	confirm_cancel: bool = False,
	callback_notice: str | None = None,
) -> None:
	booking = await booking_service.get_booking_by_id(booking_id)
	if booking is None:
		await callback.answer("Заявка не найдена.", show_alert=True)
		return

	text = build_booking_card_text(booking=booking)
	reply_markup = build_admin_booking_card_keyboard(
		booking_id=booking.id,
		current_status=booking.status,
		source=source,
		page=page,
		telegram_username=booking.telegram_username,
		confirm_cancel=confirm_cancel,
	)
	await edit_or_send_admin_view(callback, text=text, reply_markup=reply_markup)
	if callback_notice is None:
		await callback.answer()
	else:
		await callback.answer(callback_notice)


async def show_excursions_list(callback: CallbackQuery, *, answer_callback: bool = True) -> None:
	excursions = await excursion_service.list_effective_excursions(include_inactive=True)
	await edit_or_send_admin_view(
		callback,
		text=build_admin_excursions_list_text(),
		reply_markup=build_admin_excursion_list_keyboard(excursions),
	)
	if answer_callback:
		await callback.answer()


async def show_excursion_card(callback: CallbackQuery, excursion_id: str, *, notice: str | None = None) -> None:
	excursion = await excursion_service.get_effective_excursion(excursion_id)
	if excursion is None:
		await callback.answer("Экскурсия не найдена. Возвращаю к списку.", show_alert=True)
		await show_excursions_list(callback, answer_callback=False)
		return

	await edit_or_send_admin_view(
		callback,
		text=build_admin_excursion_card_text(
			excursion_title=excursion.title,
			time=excursion.time,
			price=excursion.price,
			description=excursion.description,
			included=excursion.included,
			is_active=excursion.is_active,
		),
		reply_markup=build_admin_excursion_card_keyboard(excursion),
	)
	if notice is None:
		await callback.answer()
	else:
		await callback.answer(notice)


async def show_excursion_photo_screen(callback: CallbackQuery, excursion_id: str, *, notice: str | None = None) -> None:
	excursion = await excursion_service.get_effective_excursion(excursion_id)
	if excursion is None:
		await callback.answer("Экскурсия не найдена. Возвращаю к списку.", show_alert=True)
		await show_excursions_list(callback, answer_callback=False)
		return

	override = await excursion_service.repository.get_excursion_override(excursion_id)
	has_custom_photo = bool(override and override.image_path)
	source = await excursion_service.get_excursion_image_source(excursion_id)

	await edit_or_send_admin_view(
		callback,
		text=build_admin_excursion_photo_screen_text(source),
		reply_markup=build_admin_excursion_photo_keyboard(excursion_id, has_custom_photo=has_custom_photo),
	)
	if notice is None:
		await callback.answer()
	else:
		await callback.answer(notice)


async def send_current_excursion_photo(message: Message, excursion_id: str) -> None:
	try:
		image_path, source = await excursion_service.resolve_excursion_media(excursion_id)
	except ValueError:
		await message.answer("Экскурсия не найдена. Откройте список экскурсий снова.")
		return

	caption = Text(
		"👁 ",
		Bold("Текущая фотография"),
		"\n\n",
		build_admin_excursion_photo_status_text(source),
	).as_html()

	if image_path.exists():
		await message.answer_photo(
			photo=FSInputFile(str(image_path)),
			caption=caption,
			parse_mode=ParseMode.HTML,
		)
		return

	await message.answer(caption, parse_mode=ParseMode.HTML)


async def save_excursion_photo_from_message(message: Message, excursion_id: str) -> bool:
	if not message.photo:
		await message.answer(
			"Нужна именно фотография, отправленная как Telegram photo.",
			reply_markup=admin_excursion_photo_cancel_keyboard,
		)
		return False

	if not excursion_service.is_known_excursion_id(excursion_id):
		await message.answer("Экскурсия не найдена. Откройте список экскурсий снова.", reply_markup=main_menu_keyboard)
		return False

	photo = message.photo[-1]
	if photo.file_size and photo.file_size > MAX_EXCURSION_IMAGE_BYTES:
		await message.answer(
			"Файл слишком большой. Допустимый размер: до 10 МБ.",
			reply_markup=admin_excursion_photo_cancel_keyboard,
		)
		return False

	bot = message.bot
	if bot is None:
		await message.answer("Не удалось сохранить фотографию. Попробуйте ещё раз.", reply_markup=admin_excursion_photo_cancel_keyboard)
		return False

	temp_path: Path | None = None
	target_path: Path | None = None
	old_override_path: str | None = None
	new_relative_path: Path | None = None

	try:
		file = await bot.get_file(photo.file_id)
		if file.file_size and file.file_size > MAX_EXCURSION_IMAGE_BYTES:
			await message.answer(
				"Файл слишком большой. Допустимый размер: до 10 МБ.",
				reply_markup=admin_excursion_photo_cancel_keyboard,
			)
			return False

		extension = _guess_image_extension(file.file_path)
		if extension not in ALLOWED_TELEGRAM_IMAGE_EXTENSIONS:
			extension = ".jpg"

		target_dir = excursion_service.ensure_excursion_media_dir(excursion_id)
		new_relative_path = excursion_service.build_excursion_media_relative_path(excursion_id, extension)
		target_path = (excursion_service.project_root / new_relative_path).resolve()

		with NamedTemporaryFile(prefix="upload_", suffix=extension, dir=str(target_dir), delete=False) as temp_file:
			temp_path = Path(temp_file.name)

		if not file.file_path:
			raise RuntimeError("Telegram file path is empty")
		await bot.download_file(file.file_path, destination=str(temp_path))

		if not temp_path.exists() or temp_path.stat().st_size == 0:
			raise RuntimeError("Downloaded photo is empty")

		override = await excursion_service.repository.get_excursion_override(excursion_id)
		old_override_path = override.image_path if override else None

		os.replace(temp_path, target_path)
		temp_path = None

		await excursion_service.set_excursion_image_path(excursion_id, new_relative_path.as_posix())

		if old_override_path and old_override_path != new_relative_path.as_posix():
			excursion_service.remove_custom_image_file(old_override_path)

		return True
	except Exception:
		logger.exception("Failed to save excursion photo for %s", excursion_id)
		if temp_path and temp_path.exists():
			try:
				temp_path.unlink()
			except OSError:
				logger.debug("Failed to cleanup temp photo file: %s", temp_path, exc_info=True)
		if target_path and new_relative_path:
			stored = new_relative_path.as_posix()
			current = await excursion_service.repository.get_excursion_override(excursion_id)
			if current and current.image_path != stored:
				try:
					if target_path.exists():
						target_path.unlink()
				except OSError:
					logger.debug("Failed to cleanup failed target photo file: %s", target_path, exc_info=True)

		await message.answer(
			"Не удалось сохранить фотографию. Попробуйте ещё раз.",
			reply_markup=admin_excursion_photo_cancel_keyboard,
		)
		return False


async def send_excursion_preview_messages(message: Message, excursion_id: str) -> None:
	excursion = await excursion_service.get_effective_excursion(excursion_id)
	if excursion is None:
		await message.answer("Экскурсия не найдена. Открываю список управления.")
		await message.answer(
			build_admin_excursions_list_text(),
			parse_mode=ParseMode.HTML,
			reply_markup=build_admin_excursion_list_keyboard(
				await excursion_service.list_effective_excursions(include_inactive=True)
			),
		)
		return

	await message.answer(
		Text(
			"👁 ",
			Bold("Предпросмотр для клиента"),
			"\n\n",
			"Так карточка будет выглядеть в каталоге после публикации изменений.",
		).as_html(),
		parse_mode=ParseMode.HTML,
	)

	if not excursion.is_active:
		await message.answer(
			Text(
				"🔴 ",
				Bold("Экскурсия сейчас скрыта."),
				"\n",
				"Клиенты не видят её в каталоге и подборе.",
			).as_html(),
			parse_mode=ParseMode.HTML,
		)

	caption, extra_messages = build_excursion_content(excursion)
	image_path = resolve_excursion_image_path(excursion)
	reply_markup = build_admin_excursion_preview_keyboard(excursion_id)

	if image_path.exists():
		await message.answer_photo(
			photo=FSInputFile(str(image_path)),
			caption=caption,
			parse_mode=ParseMode.HTML,
			reply_markup=reply_markup,
		)
	else:
		await message.answer(
			caption,
			parse_mode=ParseMode.HTML,
			reply_markup=reply_markup,
		)

	for extra in extra_messages:
		await message.answer(extra, parse_mode=ParseMode.HTML)


async def refresh_excursion_preview(callback: CallbackQuery, excursion_id: str) -> None:
	if callback.message is None:
		await callback.answer("Предпросмотр недоступен.", show_alert=True)
		return

	excursion = await excursion_service.get_effective_excursion(excursion_id)
	if excursion is None:
		await callback.answer("Экскурсия не найдена. Возвращаю к списку.", show_alert=True)
		await show_excursions_list(callback, answer_callback=False)
		return

	caption, extra_messages = build_excursion_content(excursion)
	image_path = resolve_excursion_image_path(excursion)
	reply_markup = build_admin_excursion_preview_keyboard(excursion_id)

	preview_header = Text(
		"👁 ",
		Bold("Предпросмотр для клиента"),
		"\n\n",
		"Так карточка будет выглядеть в каталоге после публикации изменений.",
	).as_html()
	if not excursion.is_active:
		preview_header = Text(
			preview_header,
			"\n\n",
			"🔴 ",
			Bold("Экскурсия сейчас скрыта."),
			"\n",
			"Клиенты не видят её в каталоге и подборе.",
		).as_html()

	try:
		if callback.message.photo and image_path.exists():
			await callback.message.edit_media(
				media=InputMediaPhoto(
					media=FSInputFile(str(image_path)),
					caption=caption,
					parse_mode=ParseMode.HTML,
				),
				reply_markup=reply_markup,
			)
		elif not callback.message.photo:
			await callback.message.edit_text(
				caption,
				parse_mode=ParseMode.HTML,
				reply_markup=reply_markup,
			)
		else:
			raise TelegramBadRequest("Cannot safely replace media")
	except TelegramBadRequest:
		try:
			await callback.message.delete()
		except TelegramBadRequest:
			logger.debug("Failed to delete old preview message", exc_info=True)

		await callback.message.answer(preview_header, parse_mode=ParseMode.HTML)
		if image_path.exists():
			await callback.message.answer_photo(
				photo=FSInputFile(str(image_path)),
				caption=caption,
				parse_mode=ParseMode.HTML,
				reply_markup=reply_markup,
			)
		else:
			await callback.message.answer(
				caption,
				parse_mode=ParseMode.HTML,
				reply_markup=reply_markup,
			)

	for extra in extra_messages:
		await callback.message.answer(extra, parse_mode=ParseMode.HTML)

	await callback.answer("Предпросмотр обновлён")


@router.message(Command("admin"))
async def open_admin_panel(message: Message) -> None:
	if not await ensure_admin_message_access(message, action="/admin"):
		return
	await show_admin_menu_message(message)


@router.callback_query(F.data == "admin:menu")
async def open_admin_menu_from_callback(callback: CallbackQuery, state: FSMContext) -> None:
	if not await ensure_admin_callback_access(callback, action="admin:menu"):
		return
	await clear_admin_search_state(state)
	await clear_admin_excursion_edit_state(state)
	await edit_or_send_admin_view(
		callback,
		text=build_admin_menu_text(),
		reply_markup=build_admin_menu_keyboard(),
	)
	await callback.answer()


@router.callback_query(F.data == "admin:filters:status")
async def open_status_filters(callback: CallbackQuery) -> None:
	if not await ensure_admin_callback_access(callback, action="admin:filters:status"):
		return
	await edit_or_send_admin_view(
		callback,
		text=build_status_filters_text(),
		reply_markup=build_admin_status_filters_keyboard(),
	)
	await callback.answer()


@router.callback_query(F.data.startswith("admin:list:"))
async def open_admin_list(callback: CallbackQuery) -> None:
	if not await ensure_admin_callback_access(callback, action="admin:list"):
		return

	parts = (callback.data or "").split(":")
	if len(parts) != 4:
		await callback.answer("Действие недоступно.", show_alert=True)
		return

	source = parts[2]
	page = sanitize_page(parts[3])
	if page is None:
		await callback.answer("Действие недоступно.", show_alert=True)
		return

	await show_bookings_list(callback, source=source, requested_page=page)


@router.callback_query(F.data.startswith("admin:booking:"))
async def open_admin_booking(callback: CallbackQuery) -> None:
	if not await ensure_admin_callback_access(callback, action="admin:booking"):
		return

	parts = (callback.data or "").split(":")
	if len(parts) != 5:
		await callback.answer("Действие недоступно.", show_alert=True)
		return

	booking_id_raw, source, page_raw = parts[2], parts[3], parts[4]
	if source not in VALID_SOURCES:
		await callback.answer("Действие недоступно.", show_alert=True)
		return
	if not booking_id_raw.isdigit():
		await callback.answer("Действие недоступно.", show_alert=True)
		return
	page = sanitize_page(page_raw)
	if page is None:
		await callback.answer("Действие недоступно.", show_alert=True)
		return

	await show_booking_card(callback, booking_id=int(booking_id_raw), source=source, page=page)


@router.callback_query(F.data.startswith("admin:refresh:"))
async def refresh_admin_booking(callback: CallbackQuery) -> None:
	if not await ensure_admin_callback_access(callback, action="admin:refresh"):
		return

	parts = (callback.data or "").split(":")
	if len(parts) != 5:
		await callback.answer("Действие недоступно.", show_alert=True)
		return

	booking_id_raw, source, page_raw = parts[2], parts[3], parts[4]
	if source not in VALID_SOURCES:
		await callback.answer("Действие недоступно.", show_alert=True)
		return
	if not booking_id_raw.isdigit():
		await callback.answer("Действие недоступно.", show_alert=True)
		return
	page = sanitize_page(page_raw)
	if page is None:
		await callback.answer("Действие недоступно.", show_alert=True)
		return

	booking = await booking_service.get_booking_by_id(int(booking_id_raw))
	if booking is None:
		await callback.answer("Заявка больше не найдена.", show_alert=True)
		await show_bookings_list(callback, source=source, requested_page=page)
		return

	await show_booking_card(
		callback,
		booking_id=int(booking_id_raw),
		source=source,
		page=page,
		callback_notice="Карточка обновлена",
	)


@router.callback_query(F.data.startswith("admin:cancel_confirm:"))
async def open_cancel_confirmation(callback: CallbackQuery) -> None:
	if not await ensure_admin_callback_access(callback, action="admin:cancel_confirm"):
		return

	parts = (callback.data or "").split(":")
	if len(parts) != 5:
		await callback.answer("Действие недоступно.", show_alert=True)
		return

	booking_id_raw, source, page_raw = parts[2], parts[3], parts[4]
	if source not in VALID_SOURCES:
		await callback.answer("Действие недоступно.", show_alert=True)
		return
	if not booking_id_raw.isdigit():
		await callback.answer("Действие недоступно.", show_alert=True)
		return
	page = sanitize_page(page_raw)
	if page is None:
		await callback.answer("Действие недоступно.", show_alert=True)
		return

	await show_booking_card(callback, booking_id=int(booking_id_raw), source=source, page=page, confirm_cancel=True)


@router.callback_query(F.data.startswith("admin:status:"))
async def update_admin_booking_status(callback: CallbackQuery) -> None:
	if not await ensure_admin_callback_access(callback, action="admin:status"):
		return

	parts = (callback.data or "").split(":")
	if len(parts) != 6:
		await callback.answer("Действие недоступно.", show_alert=True)
		return

	booking_id_raw, status, source, page_raw = parts[2], parts[3], parts[4], parts[5]
	if source not in VALID_SOURCES:
		await callback.answer("Действие недоступно.", show_alert=True)
		return
	if not booking_id_raw.isdigit():
		await callback.answer("Действие недоступно.", show_alert=True)
		return
	if status not in BOOKING_STATUSES:
		await callback.answer("Неизвестный статус.", show_alert=True)
		return
	page = sanitize_page(page_raw)
	if page is None:
		await callback.answer("Действие недоступно.", show_alert=True)
		return

	booking_id = int(booking_id_raw)
	current = await booking_service.get_booking_by_id(booking_id)
	if current is None:
		await callback.answer("Заявка не найдена.", show_alert=True)
		return

	if current.status == status:
		await show_booking_card(
			callback,
			booking_id=booking_id,
			source=source,
			page=page,
			callback_notice="Статус уже установлен",
		)
		return

	updated = await booking_service.update_booking_status(booking_id=booking_id, status=status)
	if not updated:
		await callback.answer("Заявка не найдена.", show_alert=True)
		return

	await show_booking_card(
		callback,
		booking_id=booking_id,
		source=source,
		page=page,
		callback_notice="Статус обновлён",
	)


@router.callback_query(F.data == "admin:search:start")
async def start_admin_search(callback: CallbackQuery, state: FSMContext) -> None:
	if not await ensure_admin_callback_access(callback, action="admin:search:start"):
		return
	await state.set_state(AdminSearchStates.waiting_for_query)
	await edit_or_send_admin_view(
		callback,
		text=build_search_prompt_text(),
		reply_markup=build_admin_search_cancel_keyboard(),
	)
	await callback.answer()


@router.callback_query(F.data == "admin:search:cancel")
async def cancel_admin_search(callback: CallbackQuery, state: FSMContext) -> None:
	if not await ensure_admin_callback_access(callback, action="admin:search:cancel"):
		return
	await clear_admin_search_state(state)
	await edit_or_send_admin_view(
		callback,
		text=build_admin_menu_text(),
		reply_markup=build_admin_menu_keyboard(),
	)
	await callback.answer("Поиск отменён")


@router.message(AdminSearchStates.waiting_for_query)
async def handle_admin_search_query(message: Message, state: FSMContext) -> None:
	if not await ensure_admin_message_access(message, action="admin:search:query"):
		return

	query = " ".join((message.text or "").split()).strip()
	if not query:
		await message.answer(
			"Введите запрос для поиска.",
			reply_markup=build_admin_search_cancel_keyboard(),
		)
		return

	results = await booking_service.search_bookings(query=query, limit=20)
	await clear_admin_search_state(state)

	if not results:
		await message.answer(
			"Заявок не найдено.",
			reply_markup=build_admin_search_no_results_keyboard(),
		)
		return

	if len(results) == 1:
		booking = results[0]
		await message.answer(
			build_booking_card_text(booking=booking),
			parse_mode=ParseMode.HTML,
			reply_markup=build_admin_booking_card_keyboard(
				booking_id=booking.id,
				current_status=booking.status,
				source=ADMIN_SOURCE_ALL,
				page=1,
				telegram_username=booking.telegram_username,
			),
		)
		return

	await message.answer(
		Text(
			"🔎 ",
			Bold("Результаты поиска"),
			"\n\n",
			f"Найдено: {len(results)}",
		).as_html(),
		parse_mode=ParseMode.HTML,
		reply_markup=build_search_results_keyboard(results),
	)


@router.callback_query(F.data.startswith("admin:search:booking:"))
async def open_search_result_booking(callback: CallbackQuery) -> None:
	if not await ensure_admin_callback_access(callback, action="admin:search:booking"):
		return

	parts = (callback.data or "").split(":")
	if len(parts) != 4:
		await callback.answer("Действие недоступно.", show_alert=True)
		return

	booking_id_raw = parts[3]
	if not booking_id_raw.isdigit():
		await callback.answer("Действие недоступно.", show_alert=True)
		return

	await show_booking_card(
		callback,
		booking_id=int(booking_id_raw),
		source=ADMIN_SOURCE_ALL,
		page=1,
	)


@router.callback_query(F.data == "admin:exc:list")
async def open_excursion_management(callback: CallbackQuery, state: FSMContext) -> None:
	if not await ensure_admin_callback_access(callback, action="admin:exc:list"):
		return
	await clear_admin_search_state(state)
	await clear_admin_excursion_edit_state(state)
	await show_excursions_list(callback)


@router.callback_query(F.data.startswith("admin:exc:list:"))
async def open_excursion_card_from_list(callback: CallbackQuery, state: FSMContext) -> None:
	if not await ensure_admin_callback_access(callback, action="admin:exc:list:item"):
		return
	parts = (callback.data or "").split(":")
	if len(parts) != 4:
		await callback.answer("Действие недоступно. Возвращаю к списку.", show_alert=True)
		await show_excursions_list(callback, answer_callback=False)
		return

	excursion_id = parts[3].strip()
	if not excursion_id:
		await callback.answer("Действие недоступно. Возвращаю к списку.", show_alert=True)
		await show_excursions_list(callback, answer_callback=False)
		return

	await clear_admin_excursion_edit_state(state)
	await show_excursion_card(callback, excursion_id)


@router.callback_query(F.data.startswith("admin:excursion_preview:"))
async def open_excursion_preview(callback: CallbackQuery, state: FSMContext) -> None:
	if not await ensure_admin_callback_access(callback, action="admin:excursion_preview"):
		return
	parts = (callback.data or "").split(":")
	if len(parts) != 3:
		await clear_admin_excursion_edit_state(state)
		await callback.answer("Некорректный предпросмотр. Возвращаю к списку.", show_alert=True)
		await show_excursions_list(callback, answer_callback=False)
		return

	excursion_id = parts[2].strip()
	if not excursion_id:
		await clear_admin_excursion_edit_state(state)
		await callback.answer("Некорректный ID экскурсии. Возвращаю к списку.", show_alert=True)
		await show_excursions_list(callback, answer_callback=False)
		return

	if callback.message is None:
		await callback.answer("Предпросмотр недоступен.", show_alert=True)
		return

	await clear_inline_keyboard(callback.message)
	await callback.answer()
	await send_excursion_preview_messages(callback.message, excursion_id)


@router.callback_query(F.data.startswith("admin:excursion_preview_refresh:"))
async def refresh_excursion_preview_callback(callback: CallbackQuery, state: FSMContext) -> None:
	if not await ensure_admin_callback_access(callback, action="admin:excursion_preview_refresh"):
		return
	parts = (callback.data or "").split(":")
	if len(parts) != 3:
		await clear_admin_excursion_edit_state(state)
		await callback.answer("Некорректный callback обновления. Возвращаю к списку.", show_alert=True)
		await show_excursions_list(callback, answer_callback=False)
		return

	excursion_id = parts[2].strip()
	if not excursion_id:
		await clear_admin_excursion_edit_state(state)
		await callback.answer("Некорректный ID экскурсии. Возвращаю к списку.", show_alert=True)
		await show_excursions_list(callback, answer_callback=False)
		return

	await refresh_excursion_preview(callback, excursion_id)


@router.callback_query(F.data.startswith("admin:excursion_photo:"))
async def open_excursion_photo_management(callback: CallbackQuery, state: FSMContext) -> None:
	if not await ensure_admin_callback_access(callback, action="admin:excursion_photo"):
		return
	parts = (callback.data or "").split(":")
	if len(parts) != 3:
		await clear_admin_excursion_edit_state(state)
		await callback.answer("Некорректный callback фотографии. Возвращаю к списку.", show_alert=True)
		await show_excursions_list(callback, answer_callback=False)
		return

	excursion_id = parts[2].strip()
	if not excursion_id:
		await clear_admin_excursion_edit_state(state)
		await callback.answer("Некорректный ID экскурсии. Возвращаю к списку.", show_alert=True)
		await show_excursions_list(callback, answer_callback=False)
		return

	await clear_admin_excursion_edit_state(state)
	await show_excursion_photo_screen(callback, excursion_id)


@router.callback_query(F.data.startswith("admin:excursion_photo_view:"))
async def view_current_excursion_photo(callback: CallbackQuery) -> None:
	if not await ensure_admin_callback_access(callback, action="admin:excursion_photo_view"):
		return
	parts = (callback.data or "").split(":")
	if len(parts) != 3:
		await callback.answer("Действие недоступно.", show_alert=True)
		return

	excursion_id = parts[2].strip()
	if not excursion_id:
		await callback.answer("Действие недоступно.", show_alert=True)
		return

	if callback.message is None:
		await callback.answer("Действие недоступно.", show_alert=True)
		return

	await send_current_excursion_photo(callback.message, excursion_id)
	await callback.answer()


@router.callback_query(F.data.startswith("admin:excursion_photo_replace:"))
async def start_excursion_photo_replace(callback: CallbackQuery, state: FSMContext) -> None:
	if not await ensure_admin_callback_access(callback, action="admin:excursion_photo_replace"):
		return
	parts = (callback.data or "").split(":")
	if len(parts) != 3:
		await clear_admin_excursion_edit_state(state)
		await callback.answer("Действие недоступно.", show_alert=True)
		return

	excursion_id = parts[2].strip()
	if not excursion_id or not excursion_service.is_known_excursion_id(excursion_id):
		await clear_admin_excursion_edit_state(state)
		await callback.answer("Экскурсия не найдена. Возвращаю к списку.", show_alert=True)
		await show_excursions_list(callback, answer_callback=False)
		return

	await clear_admin_excursion_edit_state(state)
	await state.set_state(AdminExcursionEditStates.waiting_for_photo)
	await state.update_data(excursion_id=excursion_id)

	if callback.message:
		await clear_inline_keyboard(callback.message)
		await callback.message.answer(
			build_admin_excursion_photo_screen_text(await excursion_service.get_excursion_image_source(excursion_id)),
			parse_mode=ParseMode.HTML,
			reply_markup=admin_excursion_photo_cancel_keyboard,
		)
	await callback.answer("Ожидаю новую фотографию")


@router.callback_query(F.data.startswith("admin:excursion_photo_reset:"))
async def open_excursion_photo_reset_confirm(callback: CallbackQuery, state: FSMContext) -> None:
	if not await ensure_admin_callback_access(callback, action="admin:excursion_photo_reset"):
		return
	parts = (callback.data or "").split(":")
	if len(parts) != 3:
		await clear_admin_excursion_edit_state(state)
		await callback.answer("Действие недоступно.", show_alert=True)
		return

	excursion_id = parts[2].strip()
	if not excursion_id or not excursion_service.is_known_excursion_id(excursion_id):
		await clear_admin_excursion_edit_state(state)
		await callback.answer("Экскурсия не найдена. Возвращаю к списку.", show_alert=True)
		await show_excursions_list(callback, answer_callback=False)
		return

	override = await excursion_service.repository.get_excursion_override(excursion_id)
	if not override or not override.image_path:
		await show_excursion_photo_screen(callback, excursion_id, notice="Собственной фотографии пока нет")
		return

	await clear_admin_excursion_edit_state(state)
	await edit_or_send_admin_view(
		callback,
		text=Text(
			"⚠️ ",
			Bold("Вернуть исходную фотографию?"),
			"\n\n",
			"Загруженная администратором фотография перестанет использоваться.",
		).as_html(),
		reply_markup=build_admin_excursion_photo_reset_confirm_keyboard(excursion_id),
	)
	await callback.answer()


@router.callback_query(F.data.startswith("admin:excursion_photo_reset_confirm:"))
async def apply_excursion_photo_reset(callback: CallbackQuery, state: FSMContext) -> None:
	if not await ensure_admin_callback_access(callback, action="admin:excursion_photo_reset_confirm"):
		return
	parts = (callback.data or "").split(":")
	if len(parts) != 3:
		await clear_admin_excursion_edit_state(state)
		await callback.answer("Действие недоступно.", show_alert=True)
		return

	excursion_id = parts[2].strip()
	if not excursion_id or not excursion_service.is_known_excursion_id(excursion_id):
		await clear_admin_excursion_edit_state(state)
		await callback.answer("Экскурсия не найдена. Возвращаю к списку.", show_alert=True)
		await show_excursions_list(callback, answer_callback=False)
		return

	await clear_admin_excursion_edit_state(state)
	await excursion_service.reset_excursion_image_path(excursion_id)
	await show_excursion_photo_screen(callback, excursion_id, notice="✅ Изменения сохранены")


@router.callback_query(F.data.startswith("admin:exc:edit:"))
async def start_excursion_field_edit(callback: CallbackQuery, state: FSMContext) -> None:
	if not await ensure_admin_callback_access(callback, action="admin:exc:edit"):
		return
	parts = (callback.data or "").split(":")
	if len(parts) != 5:
		await clear_admin_excursion_edit_state(state)
		await callback.answer("Устаревший callback редактирования. Возвращаю к списку.", show_alert=True)
		await show_excursions_list(callback, answer_callback=False)
		return

	excursion_id = parts[3].strip()
	field_name = parts[4].strip()
	if not excursion_id or field_name not in EXCURSION_EDITABLE_FIELDS:
		await clear_admin_excursion_edit_state(state)
		await callback.answer("Устаревший callback редактирования. Возвращаю к списку.", show_alert=True)
		await show_excursions_list(callback, answer_callback=False)
		return

	excursion = await excursion_service.get_effective_excursion(excursion_id)
	if excursion is None:
		await clear_admin_excursion_edit_state(state)
		await callback.answer("Экскурсия не найдена. Возвращаю к списку.", show_alert=True)
		await show_excursions_list(callback, answer_callback=False)
		return

	await state.set_state(AdminExcursionEditStates.waiting_for_value)
	await state.update_data(excursion_id=excursion_id, field_name=field_name)
	current_value = get_excursion_field_current_value(excursion_id, field_name, excursion)
	await edit_or_send_admin_view(
		callback,
		text=Text(
			"✏️ ",
			Bold(f"Редактирование: {EXCURSION_EDIT_FIELD_LABELS[field_name]}"),
			"\n\n",
			Bold("Текущее значение:"),
			"\n",
			escape(current_value),
			"\n\n",
			"Отправьте новое значение сообщением.",
			"\n",
			build_excursion_field_constraints(field_name),
		).as_html(),
		reply_markup=build_admin_excursion_card_keyboard(excursion),
	)
	if callback.message:
		await callback.message.answer(
			"Для отмены используйте кнопку ниже.",
			reply_markup=admin_excursion_edit_cancel_keyboard,
		)
	await callback.answer()


@router.callback_query(F.data.startswith("admin:exc:cancel:"))
async def cancel_excursion_field_edit(callback: CallbackQuery, state: FSMContext) -> None:
	if not await ensure_admin_callback_access(callback, action="admin:exc:cancel"):
		return
	parts = (callback.data or "").split(":")
	if len(parts) != 4:
		await callback.answer("Действие недоступно.", show_alert=True)
		return
	excursion_id = parts[3].strip()
	await clear_admin_excursion_edit_state(state)
	if not excursion_id:
		await show_excursions_list(callback)
		return
	await show_excursion_card(callback, excursion_id, notice="Редактирование отменено")


@router.message(AdminExcursionEditStates.waiting_for_value, F.text == CANCEL_ADMIN_EXCURSION_EDIT_TEXT)
async def cancel_excursion_field_edit_from_reply(message: Message, state: FSMContext) -> None:
	if not await ensure_admin_message_access(message, action="admin:exc:cancel:reply"):
		return

	data = await state.get_data()
	excursion_id = str(data.get("excursion_id", "")).strip()
	await state.clear()

	if excursion_id:
		excursion = await excursion_service.get_effective_excursion(excursion_id)
		if excursion is not None:
			await message.answer(
				build_admin_excursion_card_text(
					excursion_title=excursion.title,
					time=excursion.time,
					price=excursion.price,
					description=excursion.description,
					included=excursion.included,
					is_active=excursion.is_active,
				),
				parse_mode=ParseMode.HTML,
				reply_markup=build_admin_excursion_card_keyboard(excursion),
			)
			await message.answer("Редактирование отменено.", reply_markup=main_menu_keyboard)
			return

	await message.answer("Редактирование отменено. Откройте раздел экскурсий снова.", reply_markup=main_menu_keyboard)


@router.message(AdminExcursionEditStates.waiting_for_photo, F.text == CANCEL_ADMIN_EXCURSION_PHOTO_UPLOAD_TEXT)
async def cancel_excursion_photo_upload_from_reply(message: Message, state: FSMContext) -> None:
	if not await ensure_admin_message_access(message, action="admin:exc:photo:cancel:reply"):
		return

	data = await state.get_data()
	excursion_id = str(data.get("excursion_id", "")).strip()
	await state.clear()

	if excursion_id and excursion_service.is_known_excursion_id(excursion_id):
		excursion = await excursion_service.get_effective_excursion(excursion_id)
		if excursion is not None:
			await message.answer(
				build_admin_excursion_card_text(
					excursion_title=excursion.title,
					time=excursion.time,
					price=excursion.price,
					description=excursion.description,
					included=excursion.included,
					is_active=excursion.is_active,
				),
				parse_mode=ParseMode.HTML,
				reply_markup=build_admin_excursion_card_keyboard(excursion),
			)
			await message.answer("Загрузка фотографии отменена.", reply_markup=main_menu_keyboard)
			return

	await message.answer("Загрузка фотографии отменена. Откройте раздел экскурсий снова.", reply_markup=main_menu_keyboard)


@router.message(AdminExcursionEditStates.waiting_for_photo, F.photo)
async def handle_excursion_photo_upload(message: Message, state: FSMContext) -> None:
	if not await ensure_admin_message_access(message, action="admin:exc:photo:upload"):
		return

	data = await state.get_data()
	excursion_id = str(data.get("excursion_id", "")).strip()
	if not excursion_id or not excursion_service.is_known_excursion_id(excursion_id):
		await state.clear()
		await message.answer("Сессия загрузки устарела. Откройте список экскурсий снова.", reply_markup=main_menu_keyboard)
		return

	saved = await save_excursion_photo_from_message(message, excursion_id)
	if not saved:
		return

	await state.clear()
	await message.answer("✅ Изменения сохранены", reply_markup=main_menu_keyboard)

	excursion = await excursion_service.get_effective_excursion(excursion_id)
	if excursion is None:
		await message.answer("Экскурсия не найдена. Возвращаю в админ-меню.", reply_markup=main_menu_keyboard)
		return

	await message.answer(
		build_admin_excursion_card_text(
			excursion_title=excursion.title,
			time=excursion.time,
			price=excursion.price,
			description=excursion.description,
			included=excursion.included,
			is_active=excursion.is_active,
		),
		parse_mode=ParseMode.HTML,
		reply_markup=build_admin_excursion_card_keyboard(excursion),
	)


@router.message(AdminExcursionEditStates.waiting_for_photo)
async def reject_non_photo_upload(message: Message) -> None:
	if not await ensure_admin_message_access(message, action="admin:exc:photo:invalid"):
		return

	reason = "Отправьте фотографию как Telegram photo."
	if message.video:
		reason = "Видео не поддерживается. Отправьте фотографию как Telegram photo."
	elif message.animation:
		reason = "Анимации не поддерживаются. Отправьте фотографию как Telegram photo."
	elif message.document:
		reason = "Документы сейчас не поддерживаются. Отправьте фотографию как Telegram photo."
	elif message.text:
		reason = "Текст не подходит. Отправьте фотографию как Telegram photo."

	await message.answer(reason, reply_markup=admin_excursion_photo_cancel_keyboard)


@router.message(AdminExcursionEditStates.waiting_for_value)
async def handle_excursion_field_edit_value(message: Message, state: FSMContext) -> None:
	if not await ensure_admin_message_access(message, action="admin:exc:edit:value"):
		return

	data = await state.get_data()
	excursion_id = str(data.get("excursion_id", "")).strip()
	field_name = str(data.get("field_name", "")).strip()
	if not excursion_id or field_name not in EXCURSION_EDITABLE_FIELDS:
		await state.clear()
		await message.answer("Сессия редактирования устарела. Откройте список экскурсий снова.", reply_markup=main_menu_keyboard)
		return

	value = (message.text or "").strip()
	error = validate_excursion_field_value(field_name, value)
	if error:
		await message.answer(
			f"{error}\n{build_excursion_field_constraints(field_name)}",
			reply_markup=admin_excursion_edit_cancel_keyboard,
		)
		return

	normalized = normalize_excursion_field_value(field_name, value)
	if field_name == "included":
		items = tuple(line for line in normalized.splitlines() if line.strip())
		await excursion_service.update_excursion_field(excursion_id, field_name, "\n".join(items))
	else:
		await excursion_service.update_excursion_field(excursion_id, field_name, normalized)

	await state.clear()
	excursion = await excursion_service.get_effective_excursion(excursion_id)
	if excursion is None:
		await message.answer("Экскурсия не найдена. Возвращаю в админ-меню.", reply_markup=main_menu_keyboard)
		return

	await message.answer("✅ Изменения сохранены", reply_markup=main_menu_keyboard)
	await message.answer(
		build_admin_excursion_card_text(
			excursion_title=excursion.title,
			time=excursion.time,
			price=excursion.price,
			description=excursion.description,
			included=excursion.included,
			is_active=excursion.is_active,
		),
		parse_mode=ParseMode.HTML,
		reply_markup=build_admin_excursion_card_keyboard(excursion),
	)


@router.callback_query(F.data.startswith("admin:exc:toggle:"))
async def toggle_excursion_visibility(callback: CallbackQuery) -> None:
	if not await ensure_admin_callback_access(callback, action="admin:exc:toggle"):
		return
	parts = (callback.data or "").split(":")
	if len(parts) != 4:
		await callback.answer("Действие недоступно.", show_alert=True)
		return

	excursion_id = parts[3].strip()
	excursion = await excursion_service.get_effective_excursion(excursion_id)
	if excursion is None:
		await callback.answer("Экскурсия не найдена. Возвращаю к списку.", show_alert=True)
		await show_excursions_list(callback, answer_callback=False)
		return

	if excursion.is_active:
		await edit_or_send_admin_view(
			callback,
			text=Text(
				"⚠️ ",
				Bold("Скрыть экскурсию?"),
				"\n\n",
				"Она исчезнет из каталога и подбора, но данные и заявки сохранятся.",
			).as_html(),
			reply_markup=build_admin_excursion_hide_confirm_keyboard(excursion_id),
		)
		await callback.answer()
		return

	await excursion_service.set_excursion_active(excursion_id, not excursion.is_active)
	await show_excursion_card(callback, excursion_id, notice="✅ Изменения сохранены")


@router.callback_query(F.data.startswith("admin:exc:hide_apply:"))
async def apply_hide_excursion(callback: CallbackQuery) -> None:
	if not await ensure_admin_callback_access(callback, action="admin:exc:hide_apply"):
		return
	parts = (callback.data or "").split(":")
	if len(parts) != 4:
		await callback.answer("Действие недоступно.", show_alert=True)
		return
	excursion_id = parts[3].strip()
	if not excursion_id:
		await callback.answer("Действие недоступно.", show_alert=True)
		return

	excursion = await excursion_service.get_effective_excursion(excursion_id)
	if excursion is None:
		await callback.answer("Экскурсия не найдена. Возвращаю к списку.", show_alert=True)
		await show_excursions_list(callback, answer_callback=False)
		return

	await excursion_service.set_excursion_active(excursion_id, False)
	await show_excursion_card(callback, excursion_id, notice="✅ Изменения сохранены")


@router.callback_query(F.data.startswith("admin:exc:back:"))
async def back_to_excursion_card(callback: CallbackQuery) -> None:
	if not await ensure_admin_callback_access(callback, action="admin:exc:back"):
		return
	parts = (callback.data or "").split(":")
	if len(parts) != 4:
		await callback.answer("Действие недоступно.", show_alert=True)
		return
	excursion_id = parts[3].strip()
	if not excursion_id:
		await show_excursions_list(callback)
		return
	await show_excursion_card(callback, excursion_id)


@router.callback_query(F.data.startswith("admin:exc:reset_all_confirm:"))
async def open_excursion_reset_confirm(callback: CallbackQuery) -> None:
	if not await ensure_admin_callback_access(callback, action="admin:exc:reset_all_confirm"):
		return
	parts = (callback.data or "").split(":")
	if len(parts) != 4:
		await callback.answer("Действие недоступно. Возвращаю к списку.", show_alert=True)
		await show_excursions_list(callback, answer_callback=False)
		return
	excursion_id = parts[3].strip()
	if not excursion_id:
		await callback.answer("Действие недоступно. Возвращаю к списку.", show_alert=True)
		await show_excursions_list(callback, answer_callback=False)
		return

	excursion = await excursion_service.get_effective_excursion(excursion_id)
	if excursion is None:
		await callback.answer("Экскурсия не найдена. Возвращаю к списку.", show_alert=True)
		await show_excursions_list(callback, answer_callback=False)
		return

	await edit_or_send_admin_view(
		callback,
		text=Text(
			"⚠️ ",
			Bold("Сбросить все изменения?"),
			"\n\n",
			"Будут возвращены исходные значения из Python:\n",
			"• название;\n",
			"• короткое название;\n",
			"• время;\n",
			"• цена;\n",
			"• описание;\n",
			"• что включено;\n",
			"• фотография;\n",
			"• статус активности.",
		).as_html(),
		reply_markup=build_admin_excursion_reset_confirm_keyboard(excursion_id),
	)
	await callback.answer()


@router.callback_query(F.data.startswith("admin:exc:reset_menu:"))
async def stale_reset_menu_callback(callback: CallbackQuery) -> None:
	if not await ensure_admin_callback_access(callback, action="admin:exc:reset_menu"):
		return
	parts = (callback.data or "").split(":")
	if len(parts) != 4:
		await callback.answer("Кнопка устарела. Возвращаю к списку.", show_alert=True)
		await show_excursions_list(callback, answer_callback=False)
		return
	excursion_id = parts[3].strip()
	if not excursion_id:
		await callback.answer("Кнопка устарела. Возвращаю к списку.", show_alert=True)
		await show_excursions_list(callback, answer_callback=False)
		return
	await callback.answer("Кнопка устарела. Открываю подтверждение полного сброса.")
	await edit_or_send_admin_view(
		callback,
		text=Text(
			"⚠️ ",
			Bold("Сбросить все изменения?"),
			"\n\n",
			"Будут возвращены исходные значения из Python:\n",
			"• название;\n",
			"• короткое название;\n",
			"• время;\n",
			"• цена;\n",
			"• описание;\n",
			"• что включено;\n",
			"• фотография;\n",
			"• статус активности.",
		).as_html(),
		reply_markup=build_admin_excursion_reset_confirm_keyboard(excursion_id),
	)


@router.callback_query(F.data.startswith("admin:exc:reset:"))
async def stale_reset_field_callback(callback: CallbackQuery) -> None:
	if not await ensure_admin_callback_access(callback, action="admin:exc:reset"):
		return
	parts = (callback.data or "").split(":")
	if len(parts) < 4:
		await callback.answer("Кнопка устарела. Возвращаю к списку.", show_alert=True)
		await show_excursions_list(callback, answer_callback=False)
		return
	excursion_id = parts[3].strip()
	if not excursion_id:
		await callback.answer("Кнопка устарела. Возвращаю к списку.", show_alert=True)
		await show_excursions_list(callback, answer_callback=False)
		return
	await callback.answer("Кнопка устарела. Открываю подтверждение полного сброса.")
	await edit_or_send_admin_view(
		callback,
		text=Text(
			"⚠️ ",
			Bold("Сбросить все изменения?"),
			"\n\n",
			"Будут возвращены исходные значения из Python:\n",
			"• название;\n",
			"• короткое название;\n",
			"• время;\n",
			"• цена;\n",
			"• описание;\n",
			"• что включено;\n",
			"• фотография;\n",
			"• статус активности.",
		).as_html(),
		reply_markup=build_admin_excursion_reset_confirm_keyboard(excursion_id),
	)


@router.callback_query(F.data.startswith("admin:exc:reset_all_apply:"))
async def reset_excursion_all(callback: CallbackQuery) -> None:
	if not await ensure_admin_callback_access(callback, action="admin:exc:reset_all_apply"):
		return
	parts = (callback.data or "").split(":")
	if len(parts) != 4:
		await callback.answer("Действие недоступно.", show_alert=True)
		return

	excursion_id = parts[3].strip()
	if not excursion_id:
		await callback.answer("Действие недоступно.", show_alert=True)
		return

	excursion = await excursion_service.get_effective_excursion(excursion_id)
	if excursion is None:
		await callback.answer("Экскурсия не найдена. Возвращаю к списку.", show_alert=True)
		await show_excursions_list(callback, answer_callback=False)
		return

	await excursion_service.clear_excursion_override(excursion_id)
	await show_excursion_card(callback, excursion_id, notice="✅ Исходные значения восстановлены.")


@router.callback_query(F.data == "admin:stats")
async def show_admin_stats(callback: CallbackQuery) -> None:
	if not await ensure_admin_callback_access(callback, action="admin:stats"):
		return

	total = await booking_service.count_bookings()
	new = await booking_service.count_bookings(status="new")
	in_progress = await booking_service.count_bookings(status="in_progress")
	confirmed = await booking_service.count_bookings(status="confirmed")
	completed = await booking_service.count_bookings(status="completed")
	cancelled = await booking_service.count_bookings(status="cancelled")

	await edit_or_send_admin_view(
		callback,
		text=build_admin_stats_text(
			total=total,
			new=new,
			in_progress=in_progress,
			confirmed=confirmed,
			completed=completed,
			cancelled=cancelled,
		),
		reply_markup=build_admin_menu_keyboard(),
	)
	await callback.answer()


@router.callback_query(F.data == "admin:close")
async def close_admin_panel(callback: CallbackQuery, state: FSMContext) -> None:
	if not await ensure_admin_callback_access(callback, action="admin:close"):
		return
	await clear_admin_search_state(state)
	await clear_admin_excursion_edit_state(state)

	if callback.message:
		try:
			await callback.message.edit_reply_markup(reply_markup=None)
		except TelegramBadRequest:
			logger.debug("Failed to clear admin panel keyboard", exc_info=True)
		await callback.message.answer("Админ-панель закрыта.")
	await callback.answer()
