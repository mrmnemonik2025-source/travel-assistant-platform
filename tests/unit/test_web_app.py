from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from src.bot.repositories.bookings import BookingRepository
from src.bot.services.bookings import booking_service
from src.web.app import WebBookingRequest, create_booking, get_excursion, list_excursions


class WebAppTests(unittest.IsolatedAsyncioTestCase):
	async def test_catalog_exposes_active_excursions_and_images(self) -> None:
		items = await list_excursions()
		self.assertEqual(6, len(items))
		self.assertTrue(items[0]["image_url"].startswith("/static/images/excursions/"))
		self.assertTrue(items[0]["source_image_url"].startswith("/api/excursions/"))
		self.assertIn("price", items[0])

	async def test_excursion_detail_uses_shared_catalog(self) -> None:
		item = await get_excursion("asia_mix_islands")
		self.assertEqual("Asia Mix Islands", item["title"])
		self.assertTrue(item["included"])

	async def test_web_booking_is_saved_with_web_source(self) -> None:
		original_repository = booking_service.repository
		with tempfile.TemporaryDirectory() as directory:
			repository = BookingRepository(Path(directory) / "bookings.db")
			booking_service.repository = repository
			await booking_service.initialize_storage()
			try:
				with patch("src.web.app.notify_manager", new=AsyncMock(return_value=True)):
					result = await create_booking(
						WebBookingRequest(
							excursion_id="asia_mix_islands",
							customer_name="Тестовый гость",
							phone="+7 999 000-00-00",
							excursion_date="2026-08-20",
							people_count=2,
						)
					)
				row = await repository.get_booking_by_id(result["booking_id"])
				self.assertIsNotNone(row)
				self.assertEqual("web_platform", row.source)
				self.assertEqual(0, row.telegram_user_id)
				self.assertTrue(result["manager_notified"])
			finally:
				booking_service.repository = original_repository


if __name__ == "__main__":
	unittest.main()
