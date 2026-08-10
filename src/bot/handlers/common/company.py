from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.types import Message
from aiogram.utils.formatting import Bold, Text

from src.bot.keyboards.inline import about_company_keyboard


router = Router(name="common_company")


def build_about_company_text() -> str:
	return Text(
		"🌴 ",
		Bold("Asia Mix Travel"),
		"\n\n",
		"Мы помогаем гостям Вьетнама подобрать экскурсии и организовать комфортный отдых.\n\n",
		"С помощью цифрового помощника можно:\n",
		"• посмотреть каталог;\n",
		"• подобрать экскурсию;\n",
		"• оставить заявку;\n",
		"• связаться с менеджером.\n\n",
		"📍 Нячанг, Вьетнам",
	).as_html()


@router.message(F.text == "ℹ️ О компании")
async def show_about_company(message: Message) -> None:
	await message.answer(
		build_about_company_text(),
		parse_mode=ParseMode.HTML,
		reply_markup=about_company_keyboard,
	)
