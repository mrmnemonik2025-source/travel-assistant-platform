from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
import unittest

from src.bot.repositories.bookings import BookingCreateData, BookingRepository


class BookingRepositoryTests(unittest.IsolatedAsyncioTestCase):
	async def asyncSetUp(self) -> None:
		self.temp_dir = tempfile.TemporaryDirectory()
		self.db_path = Path(self.temp_dir.name) / "travel_assistant.db"
		self.repository = BookingRepository(self.db_path)
		await self.repository.initialize()

	async def asyncTearDown(self) -> None:
		self.temp_dir.cleanup()

	def _make_booking(
		self,
		*,
		telegram_username: str | None = "asia_mix",
		status: str = "new",
		customer_name: str = "Иван Петров",
		phone: str = "+79990000000",
		excursion_title: str = "Ночной круиз по заливу Нячанга",
		excursion_date: str = "25.07.2026",
	) -> BookingCreateData:
		return BookingCreateData(
			created_at="2026-07-16T10:00:00+00:00",
			status=status,
			excursion_id="emperor_cruise",
			excursion_title=excursion_title,
			customer_name=customer_name,
			phone=phone,
			excursion_date=excursion_date,
			people_count=2,
			telegram_user_id=123456789,
			telegram_username=telegram_username,
			telegram_full_name="Иван Петров",
			source="telegram_bot",
		)

	def _fetch_raw_booking_count(self) -> int:
		connection = sqlite3.connect(self.db_path)
		try:
			return int(connection.execute("SELECT COUNT(*) FROM bookings").fetchone()[0])
		finally:
			connection.close()

	async def test_initialize_creates_table(self) -> None:
		connection = sqlite3.connect(self.db_path)
		try:
			table_name = connection.execute(
				"SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'bookings'"
			).fetchone()
			self.assertIsNotNone(table_name)
		finally:
			connection.close()

	async def test_save_booking_returns_id(self) -> None:
		booking_id = await self.repository.save_booking(self._make_booking())
		self.assertEqual(1, booking_id)
		self.assertEqual(1, self._fetch_raw_booking_count())

	async def test_save_two_bookings_preserves_previous(self) -> None:
		first_id = await self.repository.save_booking(self._make_booking())
		second_id = await self.repository.save_booking(self._make_booking(telegram_username=None))
		self.assertEqual(1, first_id)
		self.assertEqual(2, second_id)
		self.assertEqual(2, self._fetch_raw_booking_count())

		first_row = await self.repository.get_booking_by_id(first_id)
		second_row = await self.repository.get_booking_by_id(second_id)
		self.assertIsNotNone(first_row)
		self.assertIsNotNone(second_row)
		self.assertEqual("asia_mix", first_row.telegram_username)
		self.assertIsNone(second_row.telegram_username)
		self.assertEqual("Иван Петров", second_row.customer_name)

	async def test_telegram_username_none_stored(self) -> None:
		booking_id = await self.repository.save_booking(self._make_booking(telegram_username=None))
		row = await self.repository.get_booking_by_id(booking_id)
		self.assertIsNotNone(row)
		self.assertIsNone(row.telegram_username)
		self.assertEqual("Иван Петров", row.customer_name)

	async def test_count_bookings_all_and_by_status(self) -> None:
		await self.repository.save_booking(self._make_booking(status="new"))
		await self.repository.save_booking(self._make_booking(status="in_progress", customer_name="Мария"))
		await self.repository.save_booking(self._make_booking(status="new", customer_name="Павел"))

		self.assertEqual(3, await self.repository.count_bookings())
		self.assertEqual(2, await self.repository.count_bookings(status="new"))
		self.assertEqual(1, await self.repository.count_bookings(status="in_progress"))
		self.assertEqual(0, await self.repository.count_bookings(status="completed"))

	async def test_list_bookings_with_limit_offset(self) -> None:
		for index in range(1, 8):
			await self.repository.save_booking(
				self._make_booking(customer_name=f"Клиент {index}")
			)

		rows = await self.repository.list_bookings(limit=5, offset=0)
		self.assertEqual(5, len(rows))
		self.assertEqual(7, rows[0].id)
		self.assertEqual(3, rows[-1].id)

		next_rows = await self.repository.list_bookings(limit=5, offset=5)
		self.assertEqual(2, len(next_rows))
		self.assertEqual(2, next_rows[0].id)
		self.assertEqual(1, next_rows[1].id)

	async def test_get_booking_by_id_returns_none_for_unknown(self) -> None:
		self.assertIsNone(await self.repository.get_booking_by_id(999))
		self.assertIsNone(await self.repository.get_booking_by_id(0))

	async def test_update_booking_status_updates_record(self) -> None:
		booking_id = await self.repository.save_booking(self._make_booking(status="new"))
		updated = await self.repository.update_booking_status(booking_id, "confirmed")
		self.assertTrue(updated)

		row = await self.repository.get_booking_by_id(booking_id)
		self.assertIsNotNone(row)
		self.assertEqual("confirmed", row.status)

	async def test_update_booking_status_unknown_id_does_not_change_data(self) -> None:
		booking_id = await self.repository.save_booking(self._make_booking(status="new"))
		updated = await self.repository.update_booking_status(999, "cancelled")
		self.assertFalse(updated)

		row = await self.repository.get_booking_by_id(booking_id)
		self.assertIsNotNone(row)
		self.assertEqual("new", row.status)
		self.assertEqual(1, self._fetch_raw_booking_count())

	async def test_search_bookings_exact_id(self) -> None:
		first_id = await self.repository.save_booking(self._make_booking(customer_name="Клиент 1"))
		await self.repository.save_booking(self._make_booking(customer_name="Клиент 2"))

		rows = await self.repository.search_bookings(str(first_id))
		self.assertEqual(1, len(rows))
		self.assertEqual(first_id, rows[0].id)

	async def test_search_bookings_partial_name_case_insensitive(self) -> None:
		await self.repository.save_booking(self._make_booking(customer_name="Иван Петров"))
		await self.repository.save_booking(self._make_booking(customer_name="Мария"))

		rows = await self.repository.search_bookings("ивАН")
		self.assertEqual(1, len(rows))
		self.assertEqual("Иван Петров", rows[0].customer_name)

	async def test_search_bookings_by_phone_partial(self) -> None:
		await self.repository.save_booking(self._make_booking(phone="+79991234567"))
		await self.repository.save_booking(self._make_booking(phone="+70000000000", customer_name="Другой"))

		rows = await self.repository.search_bookings("+7999")
		self.assertEqual(1, len(rows))
		self.assertEqual("+79991234567", rows[0].phone)

	async def test_search_bookings_by_username_partial_case_insensitive(self) -> None:
		await self.repository.save_booking(self._make_booking(telegram_username="asia_mix_admin"))
		await self.repository.save_booking(self._make_booking(telegram_username="other_user", customer_name="Другой"))

		rows = await self.repository.search_bookings("MIX")
		self.assertEqual(1, len(rows))
		self.assertEqual("asia_mix_admin", rows[0].telegram_username)

	async def test_search_bookings_no_results(self) -> None:
		await self.repository.save_booking(self._make_booking(customer_name="Иван"))

		rows = await self.repository.search_bookings("несуществующий")
		self.assertEqual([], rows)

	async def test_search_bookings_limit_20_and_latest_first(self) -> None:
		for index in range(1, 26):
			await self.repository.save_booking(
				self._make_booking(customer_name=f"Клиент {index}", telegram_username=f"user_{index}")
			)

		rows = await self.repository.search_bookings("Клиент")
		self.assertEqual(20, len(rows))
		self.assertEqual(25, rows[0].id)
		self.assertEqual(6, rows[-1].id)

	async def test_list_bookings_filter_each_status(self) -> None:
		statuses = ["new", "in_progress", "confirmed", "completed", "cancelled"]
		for index, status in enumerate(statuses, start=1):
			await self.repository.save_booking(
				self._make_booking(status=status, customer_name=f"Клиент {index}")
			)

		for status in statuses:
			rows = await self.repository.list_bookings(limit=10, offset=0, status=status)
			self.assertEqual(1, len(rows))
			self.assertEqual(status, rows[0].status)

	async def test_search_bookings_escapes_wildcards(self) -> None:
		await self.repository.save_booking(self._make_booking(customer_name="Иван_100%"))
		await self.repository.save_booking(self._make_booking(customer_name="ИванX100Y", telegram_username="another"))

		rows = await self.repository.search_bookings("_100%")
		self.assertEqual(1, len(rows))
		self.assertEqual("Иван_100%", rows[0].customer_name)
