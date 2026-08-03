from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.formatting import Bold, Text

from src.bot.data.excursions import ExcursionData
from src.bot.keyboards.inline import ABOUT_OPEN_SELECTION_CALLBACK
from src.bot.keyboards.inline.selection import (
	RESTART_SELECTION_CALLBACK,
	build_selection_result_keyboard,
	selection_no_results_keyboard,
)
from src.bot.keyboards.reply import (
	CANCEL_SELECTION_TEXT,
	AUDIENCE_OPTIONS,
	FORMAT_OPTIONS,
	INTEREST_OPTIONS,
	main_menu_keyboard,
	selection_audience_keyboard,
	selection_format_keyboard,
	selection_interest_keyboard,
)
from src.bot.states.selection import SelectionStates
from src.bot.services.excursions import excursion_service


router = Router(name="common_selection")


def build_intro_text() -> str:
	return Text(
		"✨ ",
		Bold("Подбор экскурсии"),
		"\n\n",
		"Шаг 1 из 3. С кем планируете поездку?",
	).as_html()


def build_interest_text() -> str:
	return Text(
		"✨ ",
		Bold("Подбор экскурсии"),
		"\n\n",
		"Шаг 2 из 3. Что интереснее всего?",
	).as_html()


def build_format_text() -> str:
	return Text(
		"✨ ",
		Bold("Подбор экскурсии"),
		"\n\n",
		"Шаг 3 из 3. Какой формат отдыха ближе?",
	).as_html()


def build_result_title() -> str:
	return Text(
		"✨ ",
		Bold("Мы подобрали варианты для вас"),
		"\n\n",
		"Выберите экскурсию, чтобы посмотреть подробности:",
	).as_html()


def normalize_option(option: str) -> str:
	return option.split(" ", 1)[1].strip() if " " in option else option.strip()


async def start_selection_flow(message: Message, state: FSMContext) -> None:
	await state.clear()
	await state.set_state(SelectionStates.waiting_for_audience)
	await message.answer(
		build_intro_text(),
		parse_mode=ParseMode.HTML,
		reply_markup=selection_audience_keyboard,
	)


@router.message(F.text == "✨ Подобрать экскурсию")
async def start_selection_from_menu(message: Message, state: FSMContext) -> None:
	await start_selection_flow(message, state)


@router.callback_query(F.data == ABOUT_OPEN_SELECTION_CALLBACK)
async def start_selection_from_inline(callback: CallbackQuery, state: FSMContext) -> None:
	if callback.message:
		await start_selection_flow(callback.message, state)
	await callback.answer()


@router.callback_query(F.data == RESTART_SELECTION_CALLBACK)
async def restart_selection_from_inline(callback: CallbackQuery, state: FSMContext) -> None:
	if callback.message:
		await start_selection_flow(callback.message, state)
	await callback.answer()


@router.message(F.text == CANCEL_SELECTION_TEXT)
async def cancel_selection(message: Message, state: FSMContext) -> None:
	current_state = await state.get_state()
	if current_state not in {
		SelectionStates.waiting_for_audience.state,
		SelectionStates.waiting_for_interest.state,
		SelectionStates.waiting_for_format.state,
	}:
		return

	await state.clear()
	await message.answer(
		"Подбор отменен. Вы вернулись в главное меню.",
		reply_markup=main_menu_keyboard,
	)


@router.message(SelectionStates.waiting_for_audience)
async def handle_audience(message: Message, state: FSMContext) -> None:
	option = (message.text or "").strip()
	if option not in AUDIENCE_OPTIONS:
		await message.answer(
			"Выберите вариант кнопкой ниже.",
			reply_markup=selection_audience_keyboard,
		)
		return

	await state.update_data(audience=normalize_option(option))
	await state.set_state(SelectionStates.waiting_for_interest)
	await message.answer(
		build_interest_text(),
		parse_mode=ParseMode.HTML,
		reply_markup=selection_interest_keyboard,
	)


@router.message(SelectionStates.waiting_for_interest)
async def handle_interest(message: Message, state: FSMContext) -> None:
	option = (message.text or "").strip()
	if option not in INTEREST_OPTIONS:
		await message.answer(
			"Выберите вариант кнопкой ниже.",
			reply_markup=selection_interest_keyboard,
		)
		return

	await state.update_data(interest=normalize_option(option))
	await state.set_state(SelectionStates.waiting_for_format)
	await message.answer(
		build_format_text(),
		parse_mode=ParseMode.HTML,
		reply_markup=selection_format_keyboard,
	)


def calculate_score(excursion: ExcursionData, *, audience: str, interest: str, trip_format: str) -> int:
	score = 0
	if audience in excursion.audience:
		score += 1
	if interest in excursion.interests:
		score += 1
	if trip_format in excursion.formats:
		score += 1
	return score


@router.message(SelectionStates.waiting_for_format)
async def handle_format(message: Message, state: FSMContext) -> None:
	option = (message.text or "").strip()
	if option not in FORMAT_OPTIONS:
		await message.answer(
			"Выберите вариант кнопкой ниже.",
			reply_markup=selection_format_keyboard,
		)
		return

	data = await state.get_data()
	audience = str(data.get("audience", "")).strip()
	interest = str(data.get("interest", "")).strip()
	trip_format = normalize_option(option)
	effective_excursions = await excursion_service.list_effective_excursions()

	scored: list[tuple[int, int, ExcursionData]] = []
	for index, excursion in enumerate(effective_excursions):
		score = calculate_score(
			excursion,
			audience=audience,
			interest=interest,
			trip_format=trip_format,
		)
		if score > 0:
			scored.append((score, index, excursion))

	matches = [item[2] for item in sorted(scored, key=lambda item: (-item[0], item[1]))[:3]]
	await state.clear()

	if matches:
		await message.answer(
			build_result_title(),
			parse_mode=ParseMode.HTML,
			reply_markup=build_selection_result_keyboard(matches),
		)
	else:
		await message.answer(
			"Подходящих вариантов пока не найдено. Откройте полный каталог экскурсий.",
			reply_markup=selection_no_results_keyboard,
		)

	await message.answer("Главное меню возвращено.", reply_markup=main_menu_keyboard)
