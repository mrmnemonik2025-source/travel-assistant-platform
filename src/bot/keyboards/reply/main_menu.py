from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


main_menu_keyboard = ReplyKeyboardMarkup(
	keyboard=[
		[
			KeyboardButton(text="🏝 Каталог экскурсий"),
		],
		[
			KeyboardButton(text="✨ Подобрать экскурсию"),
			KeyboardButton(text="📝 Оставить заявку"),
		],
		[
			KeyboardButton(text="💬 Связаться с менеджером"),
			KeyboardButton(text="ℹ️ О компании"),
		],
	],
	resize_keyboard=True,
	one_time_keyboard=False,
	input_field_placeholder="Выберите, что хотите посмотреть",
)