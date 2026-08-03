from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


CANCEL_ADMIN_EXCURSION_EDIT_TEXT = "❌ Отменить редактирование"
CANCEL_ADMIN_EXCURSION_PHOTO_UPLOAD_TEXT = "❌ Отменить загрузку"


admin_excursion_edit_cancel_keyboard = ReplyKeyboardMarkup(
	keyboard=[
		[
			KeyboardButton(text=CANCEL_ADMIN_EXCURSION_EDIT_TEXT),
		],
	],
	resize_keyboard=True,
)


admin_excursion_photo_cancel_keyboard = ReplyKeyboardMarkup(
	keyboard=[
		[
			KeyboardButton(text=CANCEL_ADMIN_EXCURSION_PHOTO_UPLOAD_TEXT),
		],
	],
	resize_keyboard=True,
)
