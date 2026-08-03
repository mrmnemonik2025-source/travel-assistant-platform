from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
DATABASE_PATH = PROJECT_ROOT / "data" / "database" / "travel_assistant.db"


@dataclass(frozen=True, slots=True)
class BookingCreateData:
	created_at: str
	status: str
	excursion_id: str
	excursion_title: str
	customer_name: str
	phone: str
	excursion_date: str
	people_count: int
	telegram_user_id: int
	telegram_username: str | None
	telegram_full_name: str | None
	source: str


@dataclass(frozen=True, slots=True)
class BookingRow:
	id: int
	created_at: str
	status: str
	excursion_id: str
	excursion_title: str
	customer_name: str
	phone: str
	excursion_date: str
	people_count: int
	telegram_user_id: int
	telegram_username: str | None
	telegram_full_name: str | None
	source: str


class BookingRepository:
	def __init__(self, db_path: Path = DATABASE_PATH) -> None:
		self.db_path = db_path

	async def initialize(self) -> None:
		await asyncio.to_thread(self._initialize_sync)

	async def save_booking(self, booking: BookingCreateData) -> int:
		return await asyncio.to_thread(self._save_booking_sync, booking)

	async def get_booking_by_id(self, booking_id: int) -> BookingRow | None:
		return await asyncio.to_thread(self._get_booking_by_id_sync, booking_id)

	async def count_bookings(self, status: str | None = None) -> int:
		return await asyncio.to_thread(self._count_bookings_sync, status)

	async def list_bookings(
		self,
		*,
		limit: int,
		offset: int,
		status: str | None = None,
		order_desc: bool = True,
	) -> list[BookingRow]:
		return await asyncio.to_thread(self._list_bookings_sync, limit, offset, status, order_desc)

	async def search_bookings(self, query: str, limit: int = 20) -> list[BookingRow]:
		return await asyncio.to_thread(self._search_bookings_sync, query, limit)

	async def update_booking_status(self, booking_id: int, status: str) -> bool:
		return await asyncio.to_thread(self._update_booking_status_sync, booking_id, status)

	def _connect(self) -> sqlite3.Connection:
		connection = sqlite3.connect(self.db_path)
		connection.create_function("CASEFOLD", 1, lambda value: str(value).casefold() if value is not None else "")
		return connection

	def _initialize_sync(self) -> None:
		self.db_path.parent.mkdir(parents=True, exist_ok=True)
		connection = self._connect()
		try:
			connection.execute("PRAGMA foreign_keys = ON")
			connection.execute(
				"""
				CREATE TABLE IF NOT EXISTS bookings (
					id INTEGER PRIMARY KEY AUTOINCREMENT,
					created_at TEXT NOT NULL,
					status TEXT NOT NULL DEFAULT 'new',
					excursion_id TEXT NOT NULL,
					excursion_title TEXT NOT NULL,
					customer_name TEXT NOT NULL,
					phone TEXT NOT NULL,
					excursion_date TEXT NOT NULL,
					people_count INTEGER NOT NULL,
					telegram_user_id INTEGER NOT NULL,
					telegram_username TEXT,
					telegram_full_name TEXT,
					source TEXT NOT NULL DEFAULT 'telegram_bot'
				)
				"""
			)
			connection.execute("CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings(status)")
			connection.execute("CREATE INDEX IF NOT EXISTS idx_bookings_created_at ON bookings(created_at)")
			connection.execute("CREATE INDEX IF NOT EXISTS idx_bookings_telegram_user_id ON bookings(telegram_user_id)")
			connection.commit()
		finally:
			connection.close()

	def _save_booking_sync(self, booking: BookingCreateData) -> int:
		self.db_path.parent.mkdir(parents=True, exist_ok=True)
		connection = self._connect()
		try:
			cursor = connection.execute(
				"""
				INSERT INTO bookings (
					created_at,
					status,
					excursion_id,
					excursion_title,
					customer_name,
					phone,
					excursion_date,
					people_count,
					telegram_user_id,
					telegram_username,
					telegram_full_name,
					source
				) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
				""",
				(
					booking.created_at,
					booking.status,
					booking.excursion_id,
					booking.excursion_title,
					booking.customer_name,
					booking.phone,
					booking.excursion_date,
					booking.people_count,
					booking.telegram_user_id,
					booking.telegram_username,
					booking.telegram_full_name,
					booking.source,
				),
			)
			connection.commit()
			return int(cursor.lastrowid)
		finally:
			connection.close()

	def _get_booking_by_id_sync(self, booking_id: int) -> BookingRow | None:
		if booking_id < 1:
			return None

		connection = self._connect()
		try:
			row = connection.execute(
				"""
				SELECT
					id,
					created_at,
					status,
					excursion_id,
					excursion_title,
					customer_name,
					phone,
					excursion_date,
					people_count,
					telegram_user_id,
					telegram_username,
					telegram_full_name,
					source
				FROM bookings
				WHERE id = ?
				""",
				(booking_id,),
			).fetchone()
		finally:
			connection.close()

		if row is None:
			return None

		return BookingRow(
			id=row[0],
			created_at=row[1],
			status=row[2],
			excursion_id=row[3],
			excursion_title=row[4],
			customer_name=row[5],
			phone=row[6],
			excursion_date=row[7],
			people_count=row[8],
			telegram_user_id=row[9],
			telegram_username=row[10],
			telegram_full_name=row[11],
			source=row[12],
		)

	def _count_bookings_sync(self, status: str | None = None) -> int:
		connection = self._connect()
		try:
			if status is None:
				row = connection.execute("SELECT COUNT(*) FROM bookings").fetchone()
			else:
				row = connection.execute("SELECT COUNT(*) FROM bookings WHERE status = ?", (status,)).fetchone()
		finally:
			connection.close()

		if row is None:
			return 0
		return int(row[0])

	def _list_bookings_sync(
		self,
		limit: int,
		offset: int,
		status: str | None = None,
		order_desc: bool = True,
	) -> list[BookingRow]:
		safe_limit = max(0, limit)
		safe_offset = max(0, offset)
		order_direction = "DESC" if order_desc else "ASC"

		connection = self._connect()
		try:
			if status is None:
				rows = connection.execute(
					f"""
					SELECT
						id,
						created_at,
						status,
						excursion_id,
						excursion_title,
						customer_name,
						phone,
						excursion_date,
						people_count,
						telegram_user_id,
						telegram_username,
						telegram_full_name,
						source
					FROM bookings
					ORDER BY id {order_direction}
					LIMIT ? OFFSET ?
					""",
					(safe_limit, safe_offset),
				).fetchall()
			else:
				rows = connection.execute(
					f"""
					SELECT
						id,
						created_at,
						status,
						excursion_id,
						excursion_title,
						customer_name,
						phone,
						excursion_date,
						people_count,
						telegram_user_id,
						telegram_username,
						telegram_full_name,
						source
					FROM bookings
					WHERE status = ?
					ORDER BY id {order_direction}
					LIMIT ? OFFSET ?
					""",
					(status, safe_limit, safe_offset),
				).fetchall()
		finally:
			connection.close()

		return [
			BookingRow(
				id=row[0],
				created_at=row[1],
				status=row[2],
				excursion_id=row[3],
				excursion_title=row[4],
				customer_name=row[5],
				phone=row[6],
				excursion_date=row[7],
				people_count=row[8],
				telegram_user_id=row[9],
				telegram_username=row[10],
				telegram_full_name=row[11],
				source=row[12],
			)
			for row in rows
		]

	def _escape_like(self, value: str) -> str:
		return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

	def _search_bookings_sync(self, query: str, limit: int = 20) -> list[BookingRow]:
		search_query = query.strip()
		if not search_query:
			return []

		safe_limit = max(1, min(limit, 20))
		connection = self._connect()
		try:
			if search_query.isdigit():
				rows = connection.execute(
					"""
					SELECT
						id,
						created_at,
						status,
						excursion_id,
						excursion_title,
						customer_name,
						phone,
						excursion_date,
						people_count,
						telegram_user_id,
						telegram_username,
						telegram_full_name,
						source
					FROM bookings
					WHERE id = ?
					ORDER BY id DESC
					LIMIT ?
					""",
					(int(search_query), safe_limit),
				).fetchall()
			else:
				escaped_query = self._escape_like(search_query)
				pattern = f"%{escaped_query}%"
				pattern_folded = pattern.casefold()
				rows = connection.execute(
					"""
					SELECT
						id,
						created_at,
						status,
						excursion_id,
						excursion_title,
						customer_name,
						phone,
						excursion_date,
						people_count,
						telegram_user_id,
						telegram_username,
						telegram_full_name,
						source
					FROM bookings
					WHERE CASEFOLD(customer_name) LIKE ? ESCAPE '\\'
						OR phone LIKE ? ESCAPE '\\'
						OR CASEFOLD(telegram_username) LIKE ? ESCAPE '\\'
					ORDER BY id DESC
					LIMIT ?
					""",
					(pattern_folded, pattern, pattern_folded, safe_limit),
				).fetchall()
		finally:
			connection.close()

		return [
			BookingRow(
				id=row[0],
				created_at=row[1],
				status=row[2],
				excursion_id=row[3],
				excursion_title=row[4],
				customer_name=row[5],
				phone=row[6],
				excursion_date=row[7],
				people_count=row[8],
				telegram_user_id=row[9],
				telegram_username=row[10],
				telegram_full_name=row[11],
				source=row[12],
			)
			for row in rows
		]

	def _update_booking_status_sync(self, booking_id: int, status: str) -> bool:
		if booking_id < 1:
			return False

		connection = self._connect()
		try:
			cursor = connection.execute(
				"UPDATE bookings SET status = ? WHERE id = ?",
				(status, booking_id),
			)
			connection.commit()
			return cursor.rowcount > 0
		finally:
			connection.close()
