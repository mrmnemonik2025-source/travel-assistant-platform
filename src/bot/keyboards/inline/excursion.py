from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def build_excursion_keyboard(*, booking_callback_data: str) -> InlineKeyboardMarkup:
	return InlineKeyboardMarkup(
		inline_keyboard=[
			[
				InlineKeyboardButton(
					text="📝 Оставить заявку",
					callback_data=booking_callback_data,
				),
			],
			[
				InlineKeyboardButton(
					text="⬅️ Назад к каталогу",
					callback_data="catalog:back",
				),
			],
		],
	)