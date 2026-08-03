from __future__ import annotations

import sqlite3
import tempfile
from dataclasses import replace
from pathlib import Path
import unittest

from src.bot.data.excursions import EXCURSIONS_BY_ID
from src.bot.repositories.excursions import ExcursionOverrideRepository, ExcursionOverrideRow
from src.bot.services.excursions import ExcursionService


class ExcursionMediaRepositoryTests(unittest.IsolatedAsyncioTestCase):
	async def asyncSetUp(self) -> None:
		self.temp_dir = tempfile.TemporaryDirectory()
		self.temp_path = Path(self.temp_dir.name)
		self.db_path = self.temp_path / "travel_assistant.db"
		self.project_root = self.temp_path / "project"
		self.media_root = self.project_root / "data" / "media" / "excursions"
		self.placeholder_path = self.project_root / "data" / "images" / "excursions" / "placeholder.png"

		self.media_root.mkdir(parents=True, exist_ok=True)
		self.placeholder_path.parent.mkdir(parents=True, exist_ok=True)
		self.placeholder_path.write_bytes(b"placeholder")

		self.repository = ExcursionOverrideRepository(self.db_path)
		self.service = ExcursionService(self.repository)
		self.service.project_root = self.project_root
		self.service.media_root = self.media_root
		self.service.placeholder_image_path = self.placeholder_path
		await self.service.initialize()

	async def asyncTearDown(self) -> None:
		self.temp_dir.cleanup()

	def _write_file(self, relative_path: str, content: bytes = b"img") -> Path:
		absolute = (self.project_root / relative_path).resolve()
		absolute.parent.mkdir(parents=True, exist_ok=True)
		absolute.write_bytes(content)
		return absolute

	async def test_safe_migration_adds_image_path_column_idempotent(self) -> None:
		legacy_db = self.temp_path / "legacy.db"
		connection = sqlite3.connect(legacy_db)
		try:
			connection.execute(
				"""
				CREATE TABLE excursion_overrides (
					excursion_id TEXT PRIMARY KEY,
					title TEXT,
					short_title TEXT,
					time TEXT,
					price TEXT,
					description TEXT,
					included TEXT,
					is_active INTEGER NOT NULL DEFAULT 1,
					updated_at TEXT NOT NULL
				)
				"""
			)
			connection.execute(
				"INSERT INTO excursion_overrides (excursion_id, title, updated_at) VALUES (?, ?, ?)",
				("emperor_cruise", "Legacy", "2026-01-01T00:00:00+00:00"),
			)
			connection.commit()
		finally:
			connection.close()

		repository = ExcursionOverrideRepository(legacy_db)
		await repository.initialize()
		await repository.initialize()

		connection = sqlite3.connect(legacy_db)
		try:
			columns = {
				str(row[1])
				for row in connection.execute("PRAGMA table_info(excursion_overrides)").fetchall()
			}
			count = int(connection.execute("SELECT COUNT(*) FROM excursion_overrides").fetchone()[0])
		finally:
			connection.close()

		self.assertIn("image_path", columns)
		self.assertEqual(1, count)

	async def test_save_image_path_in_override(self) -> None:
		image_path = "data/media/excursions/emperor_cruise/current.jpg"
		await self.service.set_excursion_image_path("emperor_cruise", image_path)

		override = await self.repository.get_excursion_override("emperor_cruise")
		self.assertIsNotNone(override)
		self.assertEqual(image_path, override.image_path)

	async def test_update_image_path_without_losing_other_fields(self) -> None:
		await self.service.update_excursion_field("emperor_cruise", "title", "Новое имя")
		await self.service.set_excursion_active("emperor_cruise", False)
		await self.service.set_excursion_image_path("emperor_cruise", "data/media/excursions/emperor_cruise/current.jpg")

		override = await self.repository.get_excursion_override("emperor_cruise")
		self.assertIsNotNone(override)
		self.assertEqual("Новое имя", override.title)
		self.assertFalse(override.is_active)
		self.assertEqual("data/media/excursions/emperor_cruise/current.jpg", override.image_path)

	async def test_reset_only_image_path(self) -> None:
		await self.service.update_excursion_field("emperor_cruise", "title", "Сохранить")
		await self.service.set_excursion_image_path("emperor_cruise", "data/media/excursions/emperor_cruise/current.jpg")

		await self.service.reset_excursion_image_path("emperor_cruise")

		override = await self.repository.get_excursion_override("emperor_cruise")
		self.assertIsNotNone(override)
		self.assertEqual("Сохранить", override.title)
		self.assertIsNone(override.image_path)

	def test_override_has_priority_over_base_image(self) -> None:
		base_rel = "data/images/excursions/base.jpg"
		override_rel = "data/media/excursions/emperor_cruise/current.jpg"
		self._write_file(base_rel)
		self._write_file(override_rel)

		base = replace(EXCURSIONS_BY_ID["emperor_cruise"], image_path=base_rel)
		override = ExcursionOverrideRow(
			excursion_id="emperor_cruise",
			title=None,
			short_title=None,
			time=None,
			price=None,
			description=None,
			included=None,
			image_path=override_rel,
			is_active=True,
			updated_at="2026-01-01T00:00:00+00:00",
		)

		effective = self.service._apply_override(base, override)
		self.assertEqual(override_rel, effective.image_path)

	def test_fallback_to_base_image_when_override_file_missing(self) -> None:
		base_rel = "data/images/excursions/base.jpg"
		self._write_file(base_rel)

		base = replace(EXCURSIONS_BY_ID["emperor_cruise"], image_path=base_rel)
		override = ExcursionOverrideRow(
			excursion_id="emperor_cruise",
			title=None,
			short_title=None,
			time=None,
			price=None,
			description=None,
			included=None,
			image_path="data/media/excursions/emperor_cruise/current.jpg",
			is_active=True,
			updated_at="2026-01-01T00:00:00+00:00",
		)

		effective = self.service._apply_override(base, override)
		self.assertEqual(base_rel, effective.image_path)

	def test_fallback_to_placeholder_when_no_base_image(self) -> None:
		base = replace(EXCURSIONS_BY_ID["emperor_cruise"], image_path=None)
		override = ExcursionOverrideRow(
			excursion_id="emperor_cruise",
			title=None,
			short_title=None,
			time=None,
			price=None,
			description=None,
			included=None,
			image_path="data/media/excursions/emperor_cruise/current.jpg",
			is_active=True,
			updated_at="2026-01-01T00:00:00+00:00",
		)

		effective = self.service._apply_override(base, override)
		resolved = self.service.resolve_media_path_for_excursion(effective)
		self.assertEqual(self.placeholder_path, resolved)

	def test_missing_override_file_does_not_crash(self) -> None:
		base = replace(EXCURSIONS_BY_ID["emperor_cruise"], image_path=None)
		override = ExcursionOverrideRow(
			excursion_id="emperor_cruise",
			title=None,
			short_title=None,
			time=None,
			price=None,
			description=None,
			included=None,
			image_path="data/media/excursions/emperor_cruise/missing.jpg",
			is_active=True,
			updated_at="2026-01-01T00:00:00+00:00",
		)

		effective = self.service._apply_override(base, override)
		resolved = self.service.resolve_media_path_for_excursion(effective)
		self.assertEqual(self.placeholder_path, resolved)

	async def test_clear_override_resets_photo_only_for_selected_excursion(self) -> None:
		emperor_rel = "data/media/excursions/emperor_cruise/current.jpg"
		asia_rel = "data/media/excursions/asia_mix_islands/current.jpg"
		self._write_file(emperor_rel)
		self._write_file(asia_rel)

		await self.service.set_excursion_image_path("emperor_cruise", emperor_rel)
		await self.service.set_excursion_image_path("asia_mix_islands", asia_rel)

		await self.service.clear_excursion_override("emperor_cruise")

		self.assertFalse((self.project_root / emperor_rel).exists())
		self.assertTrue((self.project_root / asia_rel).exists())
		self.assertIsNone(await self.repository.get_excursion_override("emperor_cruise"))
		asia_override = await self.repository.get_excursion_override("asia_mix_islands")
		self.assertIsNotNone(asia_override)
		self.assertEqual(asia_rel, asia_override.image_path)

	async def test_photos_of_different_excursions_do_not_mix(self) -> None:
		emperor_rel = "data/media/excursions/emperor_cruise/current.jpg"
		asia_rel = "data/media/excursions/asia_mix_islands/current.jpg"
		await self.service.set_excursion_image_path("emperor_cruise", emperor_rel)
		await self.service.set_excursion_image_path("asia_mix_islands", asia_rel)

		emperor = await self.repository.get_excursion_override("emperor_cruise")
		asia = await self.repository.get_excursion_override("asia_mix_islands")
		self.assertIsNotNone(emperor)
		self.assertIsNotNone(asia)
		self.assertEqual(emperor_rel, emperor.image_path)
		self.assertEqual(asia_rel, asia.image_path)

	async def test_unknown_excursion_id_is_rejected(self) -> None:
		with self.assertRaises(ValueError):
			await self.service.set_excursion_image_path("unknown", "data/media/excursions/unknown/current.jpg")

		with self.assertRaises(ValueError):
			self.service.build_excursion_media_relative_path("unknown", ".jpg")

	async def test_path_escape_is_rejected(self) -> None:
		with self.assertRaises(ValueError):
			await self.service.set_excursion_image_path("emperor_cruise", "../outside.jpg")

		with self.assertRaises(ValueError):
			self.service.build_excursion_media_relative_path("emperor_cruise", ".exe")
