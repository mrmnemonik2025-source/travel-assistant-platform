from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.bot.data.excursions import ExcursionData


def build_catalog_keyboard(excursions: list[ExcursionData]) -> InlineKeyboardMarkup:
	inline_keyboard: list[list[InlineKeyboardButton]] = []
	for excursion in excursions:
		inline_keyboard.append(
			[
				InlineKeyboardButton(
					text=excursion.short_title,
					callback_data=f"excursion:{excursion.id}",
				),
			]
		)

	inline_keyboard.append(
		[
			InlineKeyboardButton(
				text="⬅️ Назад в главное меню",
				callback_data="navigation:main_menu",
			),
		]
	)
	return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)