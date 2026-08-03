from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


CANCEL_SELECTION_TEXT = "❌ Отменить подбор"

AUDIENCE_OPTIONS: tuple[str, ...] = (
	"👤 Один",
	"❤️ Пара",
	"👨‍👩‍👧 Семья",
	"👥 Компания",
)

INTEREST_OPTIONS: tuple[str, ...] = (
	"🏝 Острова и пляжи",
	"🐠 Дайвинг и снорклинг",
	"🏔 Природа и горы",
	"🎢 Развлечения",
	"🌃 Вечерняя программа",
)

FORMAT_OPTIONS: tuple[str, ...] = (
	"😌 Спокойный отдых",
	"⚡ Активный отдых",
	"💎 VIP / комфорт",
	"🎉 Яркие впечатления",
)

selection_audience_keyboard = ReplyKeyboardMarkup(
	keyboard=[
		[KeyboardButton(text=AUDIENCE_OPTIONS[0]), KeyboardButton(text=AUDIENCE_OPTIONS[1])],
		[KeyboardButton(text=AUDIENCE_OPTIONS[2]), KeyboardButton(text=AUDIENCE_OPTIONS[3])],
		[KeyboardButton(text=CANCEL_SELECTION_TEXT)],
	],
	resize_keyboard=True,
	one_time_keyboard=False,
)

selection_interest_keyboard = ReplyKeyboardMarkup(
	keyboard=[
		[KeyboardButton(text=INTEREST_OPTIONS[0])],
		[KeyboardButton(text=INTEREST_OPTIONS[1])],
		[KeyboardButton(text=INTEREST_OPTIONS[2])],
		[KeyboardButton(text=INTEREST_OPTIONS[3])],
		[KeyboardButton(text=INTEREST_OPTIONS[4])],
		[KeyboardButton(text=CANCEL_SELECTION_TEXT)],
	],
	resize_keyboard=True,
	one_time_keyboard=False,
)

selection_format_keyboard = ReplyKeyboardMarkup(
	keyboard=[
		[KeyboardButton(text=FORMAT_OPTIONS[0]), KeyboardButton(text=FORMAT_OPTIONS[1])],
		[KeyboardButton(text=FORMAT_OPTIONS[2]), KeyboardButton(text=FORMAT_OPTIONS[3])],
		[KeyboardButton(text=CANCEL_SELECTION_TEXT)],
	],
	resize_keyboard=True,
	one_time_keyboard=False,
)
