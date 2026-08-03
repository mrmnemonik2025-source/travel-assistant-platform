from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
import unittest

from src.bot.data.excursions import EXCURSIONS_BY_ID
from src.bot.repositories.excursions import ExcursionOverrideRepository
from src.bot.services.excursions import ExcursionService


class ExcursionServiceTests(unittest.IsolatedAsyncioTestCase):
	async def asyncSetUp(self) -> None:
		self.temp_dir = tempfile.TemporaryDirectory()
		self.db_path = Path(self.temp_dir.name) / "travel_assistant.db"
		self.repository = ExcursionOverrideRepository(self.db_path)
		self.service = ExcursionService(self.repository)
		await self.service.initialize()

	async def asyncTearDown(self) -> None:
		self.temp_dir.cleanup()

	def _table_exists(self, table_name: str) -> bool:
		connection = sqlite3.connect(self.db_path)
		try:
			row = connection.execute(
				"SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
				(table_name,),
			).fetchone()
			return row is not None
		finally:
			connection.close()

	async def test_initialize_creates_override_table(self) -> None:
		self.assertTrue(self._table_exists("excursion_overrides"))

	async def test_update_field_overrides_title(self) -> None:
		await self.service.update_excursion_field("emperor_cruise", "title", "Новый заголовок")

		effective = await self.service.get_effective_excursion("emperor_cruise")
		self.assertIsNotNone(effective)
		self.assertEqual("Новый заголовок", effective.title)

	async def test_override_change_reflected_on_repeated_reads(self) -> None:
		before = await self.service.get_effective_excursion("emperor_cruise")
		self.assertIsNotNone(before)
		self.assertNotEqual("Обновлено сразу", before.title)

		await self.service.update_excursion_field("emperor_cruise", "title", "Обновлено сразу")

		after = await self.service.get_effective_excursion("emperor_cruise")
		self.assertIsNotNone(after)
		self.assertEqual("Обновлено сразу", after.title)

	async def test_update_each_allowed_field(self) -> None:
		updates = {
			"title": "Ночной круиз премиум",
			"short_title": "Круиз премиум",
			"time": "18:00-21:00",
			"price": "3 000 000 VND",
			"description": "Новая расширенная программа с ужином.",
			"included": "трансфер\nужин\nнапитки",
		}

		for field, value in updates.items():
			await self.service.update_excursion_field("emperor_cruise", field, value)

		effective = await self.service.get_effective_excursion("emperor_cruise")
		self.assertIsNotNone(effective)
		self.assertEqual(updates["title"], effective.title)
		self.assertEqual(updates["short_title"], effective.short_title)
		self.assertEqual(updates["time"], effective.time)
		self.assertEqual(updates["price"], effective.price)
		self.assertEqual(updates["description"], effective.description)
		self.assertEqual(("трансфер", "ужин", "напитки"), effective.included)

	async def test_update_field_overrides_included_lines(self) -> None:
		await self.service.update_excursion_field("emperor_cruise", "included", "трансфер\nужин")

		effective = await self.service.get_effective_excursion("emperor_cruise")
		self.assertIsNotNone(effective)
		self.assertEqual(("трансфер", "ужин"), effective.included)

	async def test_set_excursion_inactive_hides_from_default_listing(self) -> None:
		await self.service.set_excursion_active("emperor_cruise", False)

		visible_ids = {item.id for item in await self.service.list_effective_excursions()}
		all_ids = {item.id for item in await self.service.list_effective_excursions(include_inactive=True)}

		self.assertNotIn("emperor_cruise", visible_ids)
		self.assertIn("emperor_cruise", all_ids)

	async def test_hidden_excursion_available_for_admin_preview_read(self) -> None:
		await self.service.set_excursion_active("emperor_cruise", False)

		effective = await self.service.get_effective_excursion("emperor_cruise")
		self.assertIsNotNone(effective)
		self.assertFalse(effective.is_active)

	async def test_hide_then_show_excursion(self) -> None:
		await self.service.set_excursion_active("emperor_cruise", False)
		hidden = await self.service.get_effective_excursion("emperor_cruise")
		self.assertIsNotNone(hidden)
		self.assertFalse(hidden.is_active)

		await self.service.set_excursion_active("emperor_cruise", True)
		shown = await self.service.get_effective_excursion("emperor_cruise")
		self.assertIsNotNone(shown)
		self.assertTrue(shown.is_active)

	async def test_reset_field_restores_base_value(self) -> None:
		base_title = EXCURSIONS_BY_ID["emperor_cruise"].title
		await self.service.update_excursion_field("emperor_cruise", "title", "Переопределение")
		await self.service.reset_excursion_field("emperor_cruise", "title")

		effective = await self.service.get_effective_excursion("emperor_cruise")
		self.assertIsNotNone(effective)
		self.assertEqual(base_title, effective.title)

	async def test_clear_excursion_override_removes_changes(self) -> None:
		base = EXCURSIONS_BY_ID["emperor_cruise"]
		await self.service.update_excursion_field("emperor_cruise", "short_title", "Коротко")
		await self.service.set_excursion_active("emperor_cruise", False)
		await self.service.clear_excursion_override("emperor_cruise")

		effective = await self.service.get_effective_excursion("emperor_cruise")
		self.assertIsNotNone(effective)
		self.assertEqual(base.short_title, effective.short_title)
		self.assertTrue(effective.is_active)

	async def test_reset_override_only_for_selected_excursion(self) -> None:
		await self.service.update_excursion_field("emperor_cruise", "title", "Круиз X")
		await self.service.update_excursion_field("asia_mix_islands", "title", "Острова Y")

		await self.service.clear_excursion_override("emperor_cruise")

		emperor = await self.service.get_effective_excursion("emperor_cruise")
		asia = await self.service.get_effective_excursion("asia_mix_islands")
		self.assertIsNotNone(emperor)
		self.assertIsNotNone(asia)
		self.assertEqual(EXCURSIONS_BY_ID["emperor_cruise"].title, emperor.title)
		self.assertEqual("Острова Y", asia.title)

	async def test_update_field_rejects_unknown_field(self) -> None:
		with self.assertRaises(ValueError):
			await self.service.update_excursion_field("emperor_cruise", "unknown", "value")

	async def test_overrides_do_not_mix_between_excursions(self) -> None:
		await self.service.update_excursion_field("emperor_cruise", "price", "111")
		await self.service.update_excursion_field("asia_mix_islands", "price", "222")

		emperor = await self.service.get_effective_excursion("emperor_cruise")
		asia = await self.service.get_effective_excursion("asia_mix_islands")
		self.assertIsNotNone(emperor)
		self.assertIsNotNone(asia)
		self.assertEqual("111", emperor.price)
		self.assertEqual("222", asia.price)

	async def test_get_effective_excursion_returns_none_for_unknown_id(self) -> None:
		self.assertIsNone(await self.service.get_effective_excursion("unknown"))

	async def test_fallback_to_base_when_repository_fails(self) -> None:
		class FailingRepository:
			async def initialize(self) -> None:
				return None

			async def get_excursion_override(self, excursion_id: str):
				raise RuntimeError("db unavailable")

			async def list_excursion_overrides(self):
				raise RuntimeError("db unavailable")

		service = ExcursionService(FailingRepository())
		item = await service.get_effective_excursion("emperor_cruise")
		self.assertIsNotNone(item)
		self.assertEqual(EXCURSIONS_BY_ID["emperor_cruise"].title, item.title)

		listed = await service.list_effective_excursions()
		listed_ids = {entry.id for entry in listed}
		self.assertIn("emperor_cruise", listed_ids)
