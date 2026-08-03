from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.bot.data.excursions import ExcursionData


STATUS_ICONS: dict[str, str] = {
	"new": "🆕",
	"in_progress": "🟡",
	"confirmed": "✅",
	"completed": "🏁",
	"cancelled": "❌",
}


def _truncate(value: str, limit: int = 26) -> str:
	if len(value) <= limit:
		return value
	return f"{value[: limit - 1]}…"


def _is_valid_username(username: str | None) -> bool:
	if not username:
		return False
	if not (5 <= len(username) <= 32):
		return False
	if not username[0].isalpha():
		return False
	for char in username:
		if not (char.isalnum() or char == "_"):
			return False
	return True


def _build_booking_button_label(
	*,
	booking_id: int,
	status: str,
	short_title: str,
	customer_name: str,
	excursion_date: str,
) -> str:
	status_icon = STATUS_ICONS.get(status, "❔")
	base = f"№{booking_id} · {status_icon} {_truncate(short_title, 22)} · {_truncate(customer_name, 16)} · {_truncate(excursion_date, 10)}"
	return _truncate(base, 64)


def build_admin_menu_keyboard() -> InlineKeyboardMarkup:
	return InlineKeyboardMarkup(
		inline_keyboard=[
			[
				InlineKeyboardButton(
					text="📋 Все заявки",
					callback_data="admin:list:all:1",
				),
			],
			[
				InlineKeyboardButton(
					text="🔎 Найти заявку",
					callback_data="admin:search:start",
				),
			],
			[
				InlineKeyboardButton(
					text="📂 Заявки по статусу",
					callback_data="admin:filters:status",
				),
			],
			[
				InlineKeyboardButton(
					text="🏝 Управление экскурсиями",
					callback_data="admin:exc:list",
				),
			],
			[
				InlineKeyboardButton(
					text="📊 Статистика",
					callback_data="admin:stats",
				),
			],
			[
				InlineKeyboardButton(
					text="❌ Закрыть панель",
					callback_data="admin:close",
				),
			],
		],
	)


def build_admin_status_filters_keyboard() -> InlineKeyboardMarkup:
	return InlineKeyboardMarkup(
		inline_keyboard=[
			[
				InlineKeyboardButton(text="🆕 Новые", callback_data="admin:list:status_new:1"),
			],
			[
				InlineKeyboardButton(text="🟡 В работе", callback_data="admin:list:status_in_progress:1"),
			],
			[
				InlineKeyboardButton(text="✅ Подтверждённые", callback_data="admin:list:status_confirmed:1"),
			],
			[
				InlineKeyboardButton(text="🏁 Завершённые", callback_data="admin:list:status_completed:1"),
			],
			[
				InlineKeyboardButton(text="❌ Отменённые", callback_data="admin:list:status_cancelled:1"),
			],
			[
				InlineKeyboardButton(text="🛠 В админ-меню", callback_data="admin:menu"),
			],
		],
	)


def build_admin_search_cancel_keyboard() -> InlineKeyboardMarkup:
	return InlineKeyboardMarkup(
		inline_keyboard=[
			[
				InlineKeyboardButton(text="❌ Отменить поиск", callback_data="admin:search:cancel"),
			],
		],
	)


def build_admin_search_no_results_keyboard() -> InlineKeyboardMarkup:
	return InlineKeyboardMarkup(
		inline_keyboard=[
			[
				InlineKeyboardButton(text="🔎 Повторить поиск", callback_data="admin:search:start"),
			],
			[
				InlineKeyboardButton(text="🛠 В админ-меню", callback_data="admin:menu"),
			],
		],
	)


def build_admin_booking_list_keyboard(
	*,
	rows: list[tuple[int, str, str, str, str]],
	source: str,
	page: int,
	total_pages: int,
) -> InlineKeyboardMarkup:
	inline_keyboard: list[list[InlineKeyboardButton]] = []

	for booking_id, status, short_title, customer_name, excursion_date in rows:
		inline_keyboard.append(
			[
				InlineKeyboardButton(
					text=_build_booking_button_label(
						booking_id=booking_id,
						status=status,
						short_title=short_title,
						customer_name=customer_name,
						excursion_date=excursion_date,
					),
					callback_data=f"admin:booking:{booking_id}:{source}:{page}",
				),
			]
		)

	prev_page = max(1, page - 1)
	next_page = min(total_pages, page + 1)
	inline_keyboard.append(
		[
			InlineKeyboardButton(
				text="‹",
				callback_data=f"admin:list:{source}:{prev_page}",
			),
			InlineKeyboardButton(
				text=f"{page}/{total_pages}",
				callback_data=f"admin:list:{source}:{page}",
			),
			InlineKeyboardButton(
				text="›",
				callback_data=f"admin:list:{source}:{next_page}",
			),
		]
	)

	inline_keyboard.append(
		[
			InlineKeyboardButton(
				text="🛠 В админ-меню",
				callback_data="admin:menu",
			),
		]
	)

	return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def build_admin_booking_card_keyboard(
	*,
	booking_id: int,
	current_status: str,
	source: str,
	page: int,
	telegram_username: str | None = None,
	confirm_cancel: bool = False,
) -> InlineKeyboardMarkup:
	if confirm_cancel:
		return InlineKeyboardMarkup(
			inline_keyboard=[
				[
					InlineKeyboardButton(
						text="Подтвердить отмену",
						callback_data=f"admin:status:{booking_id}:cancelled:{source}:{page}",
					),
				],
				[
					InlineKeyboardButton(
						text="⬅️ Назад",
						callback_data=f"admin:booking:{booking_id}:{source}:{page}",
					),
				],
			],
		)

	status_buttons: list[InlineKeyboardButton] = []
	if current_status != "in_progress":
		status_buttons.append(
			InlineKeyboardButton(
				text="🟡 В работу",
				callback_data=f"admin:status:{booking_id}:in_progress:{source}:{page}",
			)
		)
	if current_status != "confirmed":
		status_buttons.append(
			InlineKeyboardButton(
				text="✅ Подтвердить",
				callback_data=f"admin:status:{booking_id}:confirmed:{source}:{page}",
			)
		)
	if current_status != "completed":
		status_buttons.append(
			InlineKeyboardButton(
				text="🏁 Завершить",
				callback_data=f"admin:status:{booking_id}:completed:{source}:{page}",
			)
		)
	if current_status != "cancelled":
		status_buttons.append(
			InlineKeyboardButton(
				text="❌ Отменить",
				callback_data=f"admin:cancel_confirm:{booking_id}:{source}:{page}",
			)
		)

	inline_keyboard: list[list[InlineKeyboardButton]] = []
	if status_buttons:
		inline_keyboard.append(status_buttons)

	inline_keyboard.append(
		[
			InlineKeyboardButton(
				text="🔄 Обновить",
				callback_data=f"admin:refresh:{booking_id}:{source}:{page}",
			),
		]
	)

	if _is_valid_username(telegram_username):
		inline_keyboard.append(
			[
				InlineKeyboardButton(
					text="💬 Открыть клиента",
					url=f"https://t.me/{telegram_username}",
				),
			]
		)

	inline_keyboard.extend(
		[
			[
				InlineKeyboardButton(
					text="⬅️ Назад",
					callback_data=f"admin:list:{source}:{page}",
				),
			],
			[
				InlineKeyboardButton(
					text="🛠 В админ-меню",
					callback_data="admin:menu",
				),
			],
		]
	)

	return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def build_admin_excursion_list_keyboard(excursions: list[ExcursionData]) -> InlineKeyboardMarkup:
	rows: list[list[InlineKeyboardButton]] = []
	for excursion in excursions:
		status = "активная" if excursion.is_active else "скрытая"
		icon = "🟢" if excursion.is_active else "🔴"
		rows.append(
			[
				InlineKeyboardButton(
					text=f"{icon} {_truncate(excursion.short_title, 28)} — {status}",
					callback_data=f"admin:exc:list:{excursion.id}",
				),
			]
		)

	rows.append([InlineKeyboardButton(text="🛠 В админ-меню", callback_data="admin:menu")])
	return InlineKeyboardMarkup(inline_keyboard=rows)


def build_admin_excursion_card_keyboard(excursion: ExcursionData) -> InlineKeyboardMarkup:
	hide_show_button = InlineKeyboardButton(
		text="👁 Скрыть" if excursion.is_active else "👁 Показать",
		callback_data=f"admin:exc:toggle:{excursion.id}",
	)

	return InlineKeyboardMarkup(
		inline_keyboard=[
			[
				InlineKeyboardButton(text="👁 Предпросмотр", callback_data=f"admin:excursion_preview:{excursion.id}"),
			],
			[
				InlineKeyboardButton(text="✏️ Название", callback_data=f"admin:exc:edit:{excursion.id}:title"),
				InlineKeyboardButton(text="🏷 Короткое название", callback_data=f"admin:exc:edit:{excursion.id}:short_title"),
			],
			[
				InlineKeyboardButton(text="🕒 Время", callback_data=f"admin:exc:edit:{excursion.id}:time"),
				InlineKeyboardButton(text="💰 Цена", callback_data=f"admin:exc:edit:{excursion.id}:price"),
			],
			[
				InlineKeyboardButton(text="📝 Описание", callback_data=f"admin:exc:edit:{excursion.id}:description"),
			],
			[
				InlineKeyboardButton(text="✅ Что включено", callback_data=f"admin:exc:edit:{excursion.id}:included"),
			],
			[
				InlineKeyboardButton(text="🖼 Фотография", callback_data=f"admin:excursion_photo:{excursion.id}"),
			],
			[
				hide_show_button,
			],
			[
				InlineKeyboardButton(text="♻️ Сбросить изменения", callback_data=f"admin:exc:reset_all_confirm:{excursion.id}"),
			],
			[
				InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:exc:list"),
				InlineKeyboardButton(text="🛠 В админ-меню", callback_data="admin:menu"),
			],
		],
	)


def build_admin_excursion_photo_keyboard(excursion_id: str, *, has_custom_photo: bool) -> InlineKeyboardMarkup:
	rows: list[list[InlineKeyboardButton]] = [
		[
			InlineKeyboardButton(
				text="👁 Посмотреть текущую",
				callback_data=f"admin:excursion_photo_view:{excursion_id}",
			),
		],
		[
			InlineKeyboardButton(
				text="🖼 Заменить фотографию",
				callback_data=f"admin:excursion_photo_replace:{excursion_id}",
			),
		],
	]

	if has_custom_photo:
		rows.append(
			[
				InlineKeyboardButton(
					text="♻️ Вернуть исходную фотографию",
					callback_data=f"admin:excursion_photo_reset:{excursion_id}",
				),
			]
		)

	rows.append(
		[
			InlineKeyboardButton(
				text="⬅️ Назад",
				callback_data=f"admin:exc:back:{excursion_id}",
			),
		]
	)

	return InlineKeyboardMarkup(inline_keyboard=rows)


def build_admin_excursion_photo_reset_confirm_keyboard(excursion_id: str) -> InlineKeyboardMarkup:
	return InlineKeyboardMarkup(
		inline_keyboard=[
			[
				InlineKeyboardButton(
					text="♻️ Подтвердить",
					callback_data=f"admin:excursion_photo_reset_confirm:{excursion_id}",
				),
			],
			[
				InlineKeyboardButton(
					text="⬅️ Назад",
					callback_data=f"admin:excursion_photo:{excursion_id}",
				),
			],
		],
	)


def build_admin_excursion_preview_keyboard(excursion_id: str) -> InlineKeyboardMarkup:
	return InlineKeyboardMarkup(
		inline_keyboard=[
			[
				InlineKeyboardButton(text="✏️ К редактированию", callback_data=f"admin:exc:back:{excursion_id}"),
			],
			[
				InlineKeyboardButton(text="🔄 Обновить предпросмотр", callback_data=f"admin:excursion_preview_refresh:{excursion_id}"),
			],
			[
				InlineKeyboardButton(text="⬅️ К списку экскурсий", callback_data="admin:exc:list"),
			],
			[
				InlineKeyboardButton(text="🛠 В админ-меню", callback_data="admin:menu"),
			],
		],
	)


def build_admin_excursion_hide_confirm_keyboard(excursion_id: str) -> InlineKeyboardMarkup:
	return InlineKeyboardMarkup(
		inline_keyboard=[
			[
				InlineKeyboardButton(text="✅ Подтвердить скрытие", callback_data=f"admin:exc:hide_apply:{excursion_id}"),
			],
			[
				InlineKeyboardButton(text="⬅️ Назад", callback_data=f"admin:exc:back:{excursion_id}"),
			],
		],
	)


def build_admin_excursion_reset_confirm_keyboard(excursion_id: str) -> InlineKeyboardMarkup:
	return InlineKeyboardMarkup(
		inline_keyboard=[
			[
				InlineKeyboardButton(text="♻️ Подтвердить сброс", callback_data=f"admin:exc:reset_all_apply:{excursion_id}"),
			],
			[
				InlineKeyboardButton(text="⬅️ Назад", callback_data=f"admin:exc:back:{excursion_id}"),
			],
		],
	)
