from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


booking_result_keyboard = InlineKeyboardMarkup(
	inline_keyboard=[
		[
			InlineKeyboardButton(
				text="🏝 Вернуться в каталог",
				callback_data="catalog:back",
			),
		],
		[
			InlineKeyboardButton(
				text="🏠 Главное меню",
				callback_data="navigation:main_menu",
			),
		],
	],
)