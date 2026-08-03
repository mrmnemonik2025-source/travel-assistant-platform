from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from src.bot.repositories.bookings import BookingCreateData, BookingRepository, BookingRow


@dataclass(frozen=True, slots=True)
class BookingSubmissionData:
	excursion_id: str
	excursion_title: str
	customer_name: str
	phone: str
	excursion_date: str
	people_count: int
	telegram_user_id: int
	telegram_username: str | None
	telegram_full_name: str | None
	source: str = "telegram_bot"


class BookingService:
	def __init__(self, repository: BookingRepository | None = None) -> None:
		self.repository = repository or BookingRepository()

	async def initialize_storage(self) -> None:
		await self.repository.initialize()

	async def save_booking(self, submission: BookingSubmissionData) -> int:
		record = BookingCreateData(
			created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
			status="new",
			excursion_id=submission.excursion_id,
			excursion_title=submission.excursion_title,
			customer_name=submission.customer_name,
			phone=submission.phone,
			excursion_date=submission.excursion_date,
			people_count=submission.people_count,
			telegram_user_id=submission.telegram_user_id,
			telegram_username=submission.telegram_username,
			telegram_full_name=submission.telegram_full_name,
			source=submission.source,
		)
		return await self.repository.save_booking(record)

	async def count_bookings(self, status: str | None = None) -> int:
		return await self.repository.count_bookings(status=status)

	async def list_bookings(
		self,
		*,
		limit: int,
		offset: int,
		status: str | None = None,
		order_desc: bool = True,
	) -> list[BookingRow]:
		return await self.repository.list_bookings(
			limit=limit,
			offset=offset,
			status=status,
			order_desc=order_desc,
		)

	async def search_bookings(self, query: str, limit: int = 20) -> list[BookingRow]:
		return await self.repository.search_bookings(query=query, limit=limit)

	async def get_booking_by_id(self, booking_id: int) -> BookingRow | None:
		return await self.repository.get_booking_by_id(booking_id)

	async def update_booking_status(self, booking_id: int, status: str) -> bool:
		return await self.repository.update_booking_status(booking_id=booking_id, status=status)


booking_service = BookingService()
