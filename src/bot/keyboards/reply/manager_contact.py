from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


CANCEL_MANAGER_MESSAGE_TEXT = "❌ Отменить сообщение"

manager_contact_keyboard = ReplyKeyboardMarkup(
	keyboard=[
		[KeyboardButton(text=CANCEL_MANAGER_MESSAGE_TEXT)],
	],
	resize_keyboard=True,
	one_time_keyboard=False,
)
