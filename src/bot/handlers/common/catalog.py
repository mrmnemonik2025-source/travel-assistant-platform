import logging
import re
from html import escape
from pathlib import Path

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, FSInputFile, InputMediaPhoto, Message
from aiogram.utils.formatting import Bold, Text

from src.bot.data.excursions import ExcursionData
from src.bot.keyboards.inline import build_catalog_keyboard, build_excursion_keyboard
from src.bot.services.excursions import excursion_service


router = Router(name="common_catalog")
logger = logging.getLogger(__name__)

PLACEHOLDER_IMAGE_PATH = excursion_service.placeholder_image_path
CAPTION_LIMIT = 1024
TEXT_MESSAGE_LIMIT = 4096
UNKNOWN_VALUE = "Уточняется у менеджера"
VND_PER_USD = 26000
VND_AMOUNT_PATTERN = re.compile(r"(\d[\d\s]*)\s*₫")


def build_catalog_text() -> str:
	return Text(
		"🏝 ",
		Bold("Каталог экскурсий"),
		"\n\n",
		"Выберите экскурсию, чтобы посмотреть подробности:",
	).as_html()


def build_excursion_text(excursion: ExcursionData) -> str:
	caption, _ = build_excursion_content(excursion)
	return caption


def is_real_value(value: str | None) -> bool:
	if value is None:
		return False
	cleaned = value.strip()
	if not cleaned:
		return False
	return "TODO" not in cleaned.upper()


def normalize_lines(lines: tuple[str, ...] | None) -> list[str]:
	if not lines:
		return []
	return [line.strip() for line in lines if is_real_value(line)]


def build_list_block(icon: str, title: str, lines: list[str]) -> str | None:
	if not lines:
		return None
	items = "\n".join(f"• {escape(line)}" for line in lines)
	return f"{icon} <b>{title}:</b>\n{items}"


def append_block_with_limit(target: list[str], block: str, *, limit: int) -> None:
	if len(block) <= limit:
		target.append(block)
		return

	chunks: list[str] = []
	current_chunk = ""
	for line in block.split("\n"):
		candidate = line if not current_chunk else f"{current_chunk}\n{line}"
		if len(candidate) <= limit:
			current_chunk = candidate
		else:
			if current_chunk:
				chunks.append(current_chunk)
			current_chunk = line[:limit]
	if current_chunk:
		chunks.append(current_chunk)

	target.extend(chunks)


def split_blocks_by_limit(blocks: list[str], *, limit: int) -> tuple[str, list[str]]:
	if not blocks:
		return "", []

	caption = blocks[0]
	extra_blocks: list[str] = []

	for block in blocks[1:]:
		candidate = f"{caption}\n\n{block}"
		if len(candidate) <= limit:
			caption = candidate
		else:
			extra_blocks.append(block)

	return caption, extra_blocks


def group_extra_blocks(extra_blocks: list[str]) -> list[str]:
	if not extra_blocks:
		return []

	messages: list[str] = []
	current = ""
	for block in extra_blocks:
		candidate = block if not current else f"{current}\n\n{block}"
		if len(candidate) <= TEXT_MESSAGE_LIMIT:
			current = candidate
		else:
			if current:
				messages.append(current)
			current = block
	if current:
		messages.append(current)

	return messages


def format_price_with_usd(price_text: str) -> str:
	def replace_amount(match: re.Match[str]) -> str:
		vnd_text = " ".join(match.group(1).split())
		vnd_amount = int(vnd_text.replace(" ", ""))
		usd_amount = round(vnd_amount / VND_PER_USD)
		return f"{vnd_text} ₫ ≈ ${usd_amount}"

	return VND_AMOUNT_PATTERN.sub(replace_amount, price_text)


def build_excursion_content(excursion: ExcursionData) -> tuple[str, list[str]]:
	time_value = escape(excursion.time.strip()) if is_real_value(excursion.time) else UNKNOWN_VALUE
	price_value = (
		escape(format_price_with_usd(excursion.price.strip()))
		if is_real_value(excursion.price)
		else UNKNOWN_VALUE
	)
	title_value = escape(excursion.title)

	blocks: list[str] = [
		"\n".join(
			[
				f"<b>{title_value}</b>",
				"",
				f"🕒 <b>Время:</b> {time_value}",
				f"💰 <b>Стоимость:</b> {price_value}",
			]
		),
	]

	if is_real_value(excursion.description):
		blocks.append(escape(excursion.description.strip()))

	optional_blocks = [
		build_list_block("✅", "Включено", normalize_lines(excursion.included)),
		build_list_block("❌", "Не включено", normalize_lines(excursion.not_included)),
		build_list_block("🎒", "Что взять с собой", normalize_lines(excursion.what_to_bring)),
		build_list_block("⚠️", "Ограничения", normalize_lines(excursion.restrictions)),
	]

	if is_real_value(excursion.departure_point):
		optional_blocks.append(f"📍 <b>Отправление:</b> {escape(excursion.departure_point.strip())}")

	for block in optional_blocks:
		if block:
			append_block_with_limit(blocks, block, limit=TEXT_MESSAGE_LIMIT)

	caption, extra_blocks = split_blocks_by_limit(blocks, limit=CAPTION_LIMIT)
	return caption, group_extra_blocks(extra_blocks)


def resolve_excursion_image_path(excursion: ExcursionData) -> Path:
	return excursion_service.resolve_media_path_for_excursion(excursion)


@router.message(F.text == "🏝 Каталог экскурсий")
async def open_catalog(message: Message) -> None:
	excursions = await excursion_service.list_effective_excursions()
	await message.answer(
		build_catalog_text(),
		parse_mode=ParseMode.HTML,
		reply_markup=build_catalog_keyboard(excursions),
	)


@router.callback_query(F.data.startswith("excursion:"))
async def open_excursion_card(callback: CallbackQuery) -> None:
	excursion_id = callback.data.split(":", 1)[1] if callback.data else ""
	excursion = await excursion_service.get_effective_excursion(excursion_id)
	if excursion is None:
		await callback.answer("Экскурсия пока недоступна", show_alert=True)
		return
	if not excursion.is_active:
		await callback.answer("Экскурсия временно недоступна", show_alert=True)
		return

	if callback.message:
		image_path = resolve_excursion_image_path(excursion)
		caption, extra_messages = build_excursion_content(excursion)
		if not image_path.exists():
			logger.warning("Placeholder image file is missing: %s", image_path)
			await callback.message.answer(
				caption,
				parse_mode=ParseMode.HTML,
				reply_markup=build_excursion_keyboard(
					booking_callback_data=excursion.booking_callback_data,
				),
			)
			for extra in extra_messages:
				await callback.message.answer(extra, parse_mode=ParseMode.HTML)
			await callback.answer()
			return

		reply_markup = build_excursion_keyboard(
			booking_callback_data=excursion.booking_callback_data,
		)
		photo = FSInputFile(str(image_path))

		if callback.message.photo:
			await callback.message.edit_media(
				media=InputMediaPhoto(
					media=photo,
					caption=caption,
					parse_mode=ParseMode.HTML,
				),
				reply_markup=reply_markup,
			)
		else:
			await callback.message.answer_photo(
				photo=photo,
				caption=caption,
				parse_mode=ParseMode.HTML,
				reply_markup=reply_markup,
			)
			try:
				await callback.message.delete()
			except TelegramBadRequest:
				logger.debug("Failed to delete previous catalog message", exc_info=True)

		for extra in extra_messages:
			await callback.message.answer(extra, parse_mode=ParseMode.HTML)
	await callback.answer()


@router.callback_query(F.data == "catalog:back")
async def back_to_catalog(callback: CallbackQuery) -> None:
	excursions = await excursion_service.list_effective_excursions()
	if callback.message:
		try:
			await callback.message.edit_text(
				build_catalog_text(),
				parse_mode=ParseMode.HTML,
				reply_markup=build_catalog_keyboard(excursions),
			)
		except TelegramBadRequest:
			await callback.message.answer(
				build_catalog_text(),
				parse_mode=ParseMode.HTML,
				reply_markup=build_catalog_keyboard(excursions),
			)
			try:
				await callback.message.delete()
			except TelegramBadRequest:
				logger.debug("Failed to delete previous excursion media message", exc_info=True)
	await callback.answer()