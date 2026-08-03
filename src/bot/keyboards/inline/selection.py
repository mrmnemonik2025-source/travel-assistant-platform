from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.bot.data.excursions import ExcursionData


RESTART_SELECTION_CALLBACK = "selection:restart"


def build_selection_result_keyboard(excursions: list[ExcursionData]) -> InlineKeyboardMarkup:
	rows: list[list[InlineKeyboardButton]] = []
	for excursion in excursions:
		rows.append(
			[
				InlineKeyboardButton(
					text=f"🏝 {excursion.short_title}",
					callback_data=f"excursion:{excursion.id}",
				),
			]
		)

	rows.extend(
		[
			[
				InlineKeyboardButton(
					text="🔄 Пройти подбор заново",
					callback_data=RESTART_SELECTION_CALLBACK,
				),
			],
			[
				InlineKeyboardButton(
					text="🏠 Главное меню",
					callback_data="navigation:main_menu",
				),
			],
		]
	)
	return InlineKeyboardMarkup(inline_keyboard=rows)


selection_no_results_keyboard = InlineKeyboardMarkup(
	inline_keyboard=[
		[
			InlineKeyboardButton(
				text="🏝 Открыть каталог",
				callback_data="catalog:back",
			),
		],
		[
			InlineKeyboardButton(
				text="🔄 Пройти подбор заново",
				callback_data=RESTART_SELECTION_CALLBACK,
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
