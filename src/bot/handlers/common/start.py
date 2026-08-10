from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, FSInputFile, Message
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.formatting import Bold, Text
from pathlib import Path

from src.bot.keyboards.reply import main_menu_keyboard


router = Router(name="common_start")
WELCOME_IMAGE_PATH = Path(__file__).resolve().parents[2] / "assets" / "images" / "welcome_vietnam.png"
@router.message(Command("chatid"))
async def chat_id_command(message: Message) -> None:
    await message.answer(f"Chat ID: {message.chat.id}")

@router.message(CommandStart())
async def start_command(message: Message) -> None:
	text = Text(
		"🌴 ",
		Bold("Asia Mix Travel"),
		"\n\n",
		"Добро пожаловать во Вьетнам! 🇻🇳\n\n",
		"Я помогу подобрать интересную экскурсию и передать заявку менеджеру.",
	)
	caption = text.as_html()
	if WELCOME_IMAGE_PATH.exists():
		try:
			await message.answer_photo(
				photo=FSInputFile(str(WELCOME_IMAGE_PATH)),
				caption=caption,
				parse_mode=ParseMode.HTML,
				reply_markup=main_menu_keyboard,
			)
			return
		except Exception:
			# If media sending fails, keep /start flow functional via text fallback.
			pass

	await message.answer(
		caption,
		parse_mode=ParseMode.HTML,
		reply_markup=main_menu_keyboard,
	)


@router.callback_query(F.data.in_({"navigation:main_menu", "menu:main"}))
async def open_main_menu(callback: CallbackQuery) -> None:
	await callback.answer()

	if callback.message:
		try:
			await callback.message.edit_reply_markup(reply_markup=None)
		except TelegramBadRequest:
			try:
				await callback.message.delete()
			except TelegramBadRequest:
				pass

		await callback.message.answer(
			"🏠 Главное меню",
			reply_markup=main_menu_keyboard,
		)