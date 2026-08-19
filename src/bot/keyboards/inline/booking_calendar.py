from __future__ import annotations

import calendar
from datetime import date, timedelta

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


BOOKING_CALENDAR_PREFIX = "booking_calendar"
BOOKING_CALENDAR_IGNORE_CALLBACK = f"{BOOKING_CALENDAR_PREFIX}:ignore"
BOOKING_CALENDAR_CANCEL_CALLBACK = f"{BOOKING_CALENDAR_PREFIX}:cancel"
WEEKDAY_LABELS = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
MONTH_NAMES = (
	"Январь",
	"Февраль",
	"Март",
	"Апрель",
	"Май",
	"Июнь",
	"Июль",
	"Август",
	"Сентябрь",
	"Октябрь",
	"Ноябрь",
	"Декабрь",
)


def _month_start(month_date: date) -> date:
	return month_date.replace(day=1)


def _add_months(month_date: date, months: int) -> date:
	year = month_date.year + (month_date.month - 1 + months) // 12
	month = (month_date.month - 1 + months) % 12 + 1
	return date(year, month, 1)


def _month_label(month_date: date) -> str:
	return f"{MONTH_NAMES[month_date.month - 1]} {month_date.year}"


def _navigation_button(text: str, callback_data: str) -> InlineKeyboardButton:
	return InlineKeyboardButton(text=text, callback_data=callback_data)


def build_booking_calendar_keyboard(month_date: date) -> InlineKeyboardMarkup:
	today = date.today()
	current_month = _month_start(date.today())
	month_date = _month_start(month_date)
	max_month = _add_months(current_month, 12)
	calendar_grid = calendar.Calendar(firstweekday=0).monthdayscalendar(month_date.year, month_date.month)

	rows: list[list[InlineKeyboardButton]] = []

	prev_month = _add_months(month_date, -1)
	next_month = _add_months(month_date, 1)
	rows.append(
		[
			_navigation_button(
				"‹ предыдущий месяц",
				f"{BOOKING_CALENDAR_PREFIX}:month:{prev_month:%Y-%m}"
				if prev_month >= current_month
				else BOOKING_CALENDAR_IGNORE_CALLBACK,
			),
			_navigation_button(
				_month_label(month_date),
				BOOKING_CALENDAR_IGNORE_CALLBACK,
			),
			_navigation_button(
				"следующий месяц ›",
				f"{BOOKING_CALENDAR_PREFIX}:month:{next_month:%Y-%m}"
				if next_month <= max_month
				else BOOKING_CALENDAR_IGNORE_CALLBACK,
			),
		]
	)
	rows.append(
		[
			_navigation_button(label, BOOKING_CALENDAR_IGNORE_CALLBACK)
			for label in WEEKDAY_LABELS
		]
	)

	for week in calendar_grid:
		week_buttons: list[InlineKeyboardButton] = []
		for day in week:
			if day == 0:
				week_buttons.append(_navigation_button(" ", BOOKING_CALENDAR_IGNORE_CALLBACK))
				continue

			day_date = date(month_date.year, month_date.month, day)
			day_label = str(day)
			if day_date == today:
				day_label = f"[{day}]"
			week_buttons.append(
				_navigation_button(
					day_label,
					f"{BOOKING_CALENDAR_PREFIX}:day:{day_date:%Y-%m-%d}",
				)
			)
		rows.append(week_buttons)

	rows.append(
		[
			_navigation_button("❌ Отменить заявку", BOOKING_CALENDAR_CANCEL_CALLBACK),
		]
	)

	return InlineKeyboardMarkup(inline_keyboard=rows)
