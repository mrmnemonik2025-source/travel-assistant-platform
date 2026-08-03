from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.formatting import Bold, Text

from src.bot.keyboards.reply import main_menu_keyboard


router = Router(name="common_start")


@router.message(CommandStart())
async def start_command(message: Message) -> None:
	text = Text(
		"🌴 ",
		Bold("Asia Mix Travel"),
		"\n\n",
		"Добро пожаловать во Вьетнам! 🇻🇳\n\n",
		"Я помогу подобрать интересную экскурсию и передать заявку менеджеру.\n\n",
		"Скоро здесь появится удобное меню.",
	)
	await message.answer(
		text.as_html(),
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
			"Главное меню возвращено.",
			reply_markup=main_menu_keyboard,
		)