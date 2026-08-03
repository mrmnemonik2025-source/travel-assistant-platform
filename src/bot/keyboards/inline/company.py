from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


ABOUT_OPEN_SELECTION_CALLBACK = "selection:start"
ABOUT_CONTACT_MANAGER_CALLBACK = "manager:contact"

about_company_keyboard = InlineKeyboardMarkup(
	inline_keyboard=[
		[
			InlineKeyboardButton(
				text="🏝 Каталог экскурсий",
				callback_data="catalog:back",
			),
		],
		[
			InlineKeyboardButton(
				text="✨ Подобрать экскурсию",
				callback_data=ABOUT_OPEN_SELECTION_CALLBACK,
			),
		],
		[
			InlineKeyboardButton(
				text="💬 Связаться с менеджером",
				callback_data=ABOUT_CONTACT_MANAGER_CALLBACK,
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
