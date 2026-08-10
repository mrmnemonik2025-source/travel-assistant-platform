from __future__ import annotations

import unittest
from dataclasses import replace

from src.bot.data.excursions import EXCURSIONS_BY_ID
from src.bot.handlers.common.catalog import PLACEHOLDER_IMAGE_PATH, resolve_excursion_image_path


class CatalogRenderingTests(unittest.TestCase):
	def test_existing_image_uses_excursion_photo(self) -> None:
		excursion = EXCURSIONS_BY_ID["emperor_cruise"]
		resolved = resolve_excursion_image_path(excursion)
		self.assertEqual("night_cruise.png", resolved.name)
		self.assertTrue(resolved.exists())

	def test_missing_image_uses_placeholder_path(self) -> None:
		excursion = replace(EXCURSIONS_BY_ID["emperor_cruise"], image_path="missing.jpg")
		resolved = resolve_excursion_image_path(excursion)
		self.assertEqual(PLACEHOLDER_IMAGE_PATH, resolved)
		self.assertTrue(resolved.exists())
