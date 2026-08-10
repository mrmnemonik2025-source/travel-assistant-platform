from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


booking_phone_keyboard = ReplyKeyboardMarkup(
	keyboard=[
		[
			KeyboardButton(text="📱 Отправить контакт", request_contact=True),
		],
		[
			KeyboardButton(text="❌ Отменить заявку"),
		],
	],
	resize_keyboard=True,
	one_time_keyboard=False,
)

booking_cancel_keyboard = ReplyKeyboardMarkup(
	keyboard=[
		[
			KeyboardButton(text="❌ Отменить заявку"),
		],
	],
	resize_keyboard=True,
	one_time_keyboard=False,
)