from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.bot.repositories.bookings import DATABASE_PATH


EDITABLE_FIELDS: tuple[str, ...] = (
	"title",
	"short_title",
	"time",
	"price",
	"description",
	"included",
)

IMAGE_PATH_FIELD = "image_path"
OVERRIDABLE_FIELDS: tuple[str, ...] = EDITABLE_FIELDS + (IMAGE_PATH_FIELD,)


@dataclass(frozen=True, slots=True)
class ExcursionOverrideRow:
	excursion_id: str
	title: str | None
	short_title: str | None
	time: str | None
	price: str | None
	description: str | None
	included: str | None
	image_path: str | None
	is_active: bool
	updated_at: str


class ExcursionOverrideRepository:
	def __init__(self, db_path: Path = DATABASE_PATH) -> None:
		self.db_path = db_path

	async def initialize(self) -> None:
		await asyncio.to_thread(self._initialize_sync)

	async def get_excursion_override(self, excursion_id: str) -> ExcursionOverrideRow | None:
		return await asyncio.to_thread(self._get_excursion_override_sync, excursion_id)

	async def list_excursion_overrides(self) -> list[ExcursionOverrideRow]:
		return await asyncio.to_thread(self._list_excursion_overrides_sync)

	async def upsert_excursion_override(self, excursion_id: str, fields: dict[str, str | None]) -> None:
		await asyncio.to_thread(self._upsert_excursion_override_sync, excursion_id, fields)

	async def set_excursion_active(self, excursion_id: str, is_active: bool) -> None:
		await asyncio.to_thread(self._set_excursion_active_sync, excursion_id, is_active)

	async def reset_excursion_field(self, excursion_id: str, field_name: str) -> None:
		await asyncio.to_thread(self._reset_excursion_field_sync, excursion_id, field_name)

	async def set_excursion_image_path(self, excursion_id: str, image_path: str | None) -> None:
		await asyncio.to_thread(self._set_excursion_image_path_sync, excursion_id, image_path)

	async def reset_excursion_image_path(self, excursion_id: str) -> None:
		await asyncio.to_thread(self._reset_excursion_field_sync, excursion_id, IMAGE_PATH_FIELD)

	async def delete_excursion_override(self, excursion_id: str) -> None:
		await asyncio.to_thread(self._delete_excursion_override_sync, excursion_id)

	def _connect(self) -> sqlite3.Connection:
		return sqlite3.connect(self.db_path)

	def _initialize_sync(self) -> None:
		self.db_path.parent.mkdir(parents=True, exist_ok=True)
		connection = self._connect()
		try:
			connection.execute(
				"""
				CREATE TABLE IF NOT EXISTS excursion_overrides (
					excursion_id TEXT PRIMARY KEY,
					title TEXT,
					short_title TEXT,
					time TEXT,
					price TEXT,
					description TEXT,
					included TEXT,
					image_path TEXT,
					is_active INTEGER NOT NULL DEFAULT 1,
					updated_at TEXT NOT NULL
				)
				"""
			)
			self._ensure_column_exists_sync(connection, "excursion_overrides", "image_path", "TEXT")
			connection.commit()
		finally:
			connection.close()

	def _ensure_column_exists_sync(
		self,
		connection: sqlite3.Connection,
		table_name: str,
		column_name: str,
		column_definition: str,
	) -> None:
		rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
		existing_columns = {str(row[1]) for row in rows}
		if column_name in existing_columns:
			return
		connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")

	def _to_row(self, raw: tuple[object, ...]) -> ExcursionOverrideRow:
		return ExcursionOverrideRow(
			excursion_id=str(raw[0]),
			title=raw[1] if isinstance(raw[1], str) else None,
			short_title=raw[2] if isinstance(raw[2], str) else None,
			time=raw[3] if isinstance(raw[3], str) else None,
			price=raw[4] if isinstance(raw[4], str) else None,
			description=raw[5] if isinstance(raw[5], str) else None,
			included=raw[6] if isinstance(raw[6], str) else None,
			image_path=raw[7] if isinstance(raw[7], str) else None,
			is_active=bool(int(raw[8])),
			updated_at=str(raw[9]),
		)

	def _get_excursion_override_sync(self, excursion_id: str) -> ExcursionOverrideRow | None:
		connection = self._connect()
		try:
			row = connection.execute(
				"""
				SELECT
					excursion_id,
					title,
					short_title,
					time,
					price,
					description,
					included,
					image_path,
					is_active,
					updated_at
				FROM excursion_overrides
				WHERE excursion_id = ?
				""",
				(excursion_id,),
			).fetchone()
		finally:
			connection.close()

		if row is None:
			return None
		return self._to_row(row)

	def _list_excursion_overrides_sync(self) -> list[ExcursionOverrideRow]:
		connection = self._connect()
		try:
			rows = connection.execute(
				"""
				SELECT
					excursion_id,
					title,
					short_title,
					time,
					price,
					description,
					included,
					image_path,
					is_active,
					updated_at
				FROM excursion_overrides
				ORDER BY excursion_id ASC
				"""
			).fetchall()
		finally:
			connection.close()

		return [self._to_row(row) for row in rows]

	def _validate_fields(self, fields: dict[str, str | None]) -> dict[str, str | None]:
		validated: dict[str, str | None] = {}
		for key, value in fields.items():
			if key not in OVERRIDABLE_FIELDS:
				raise ValueError(f"Unsupported excursion field: {key}")
			validated[key] = value
		return validated

	def _upsert_excursion_override_sync(self, excursion_id: str, fields: dict[str, str | None]) -> None:
		validated = self._validate_fields(fields)
		if not validated:
			return

		existing = self._get_excursion_override_sync(excursion_id)
		data = {
			"title": existing.title if existing else None,
			"short_title": existing.short_title if existing else None,
			"time": existing.time if existing else None,
			"price": existing.price if existing else None,
			"description": existing.description if existing else None,
			"included": existing.included if existing else None,
			"image_path": existing.image_path if existing else None,
			"is_active": 1 if (existing.is_active if existing else True) else 0,
		}
		for key, value in validated.items():
			data[key] = value

		now = datetime.now(timezone.utc).isoformat(timespec="seconds")
		connection = self._connect()
		try:
			connection.execute(
				"""
				INSERT INTO excursion_overrides (
					excursion_id,
					title,
					short_title,
					time,
					price,
					description,
					included,
					image_path,
					is_active,
					updated_at
				) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
				ON CONFLICT(excursion_id) DO UPDATE SET
					title = excluded.title,
					short_title = excluded.short_title,
					time = excluded.time,
					price = excluded.price,
					description = excluded.description,
					included = excluded.included,
					image_path = excluded.image_path,
					is_active = excluded.is_active,
					updated_at = excluded.updated_at
				""",
				(
					excursion_id,
					data["title"],
					data["short_title"],
					data["time"],
					data["price"],
					data["description"],
					data["included"],
					data["image_path"],
					data["is_active"],
					now,
				),
			)
			connection.commit()
		finally:
			connection.close()

	def _set_excursion_active_sync(self, excursion_id: str, is_active: bool) -> None:
		existing = self._get_excursion_override_sync(excursion_id)
		now = datetime.now(timezone.utc).isoformat(timespec="seconds")
		connection = self._connect()
		try:
			connection.execute(
				"""
				INSERT INTO excursion_overrides (
					excursion_id,
					title,
					short_title,
					time,
					price,
					description,
					included,
					image_path,
					is_active,
					updated_at
				) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
				ON CONFLICT(excursion_id) DO UPDATE SET
					is_active = excluded.is_active,
					updated_at = excluded.updated_at
				""",
				(
					excursion_id,
					existing.title if existing else None,
					existing.short_title if existing else None,
					existing.time if existing else None,
					existing.price if existing else None,
					existing.description if existing else None,
					existing.included if existing else None,
					existing.image_path if existing else None,
					1 if is_active else 0,
					now,
				),
			)
			connection.commit()
		finally:
			connection.close()

	def _reset_excursion_field_sync(self, excursion_id: str, field_name: str) -> None:
		if field_name not in OVERRIDABLE_FIELDS:
			raise ValueError(f"Unsupported excursion field: {field_name}")

		column_map = {
			"title": "title",
			"short_title": "short_title",
			"time": "time",
			"price": "price",
			"description": "description",
			"included": "included",
			IMAGE_PATH_FIELD: IMAGE_PATH_FIELD,
		}
		column = column_map[field_name]
		now = datetime.now(timezone.utc).isoformat(timespec="seconds")

		connection = self._connect()
		try:
			connection.execute(
				f"UPDATE excursion_overrides SET {column} = NULL, updated_at = ? WHERE excursion_id = ?",
				(now, excursion_id),
			)
			connection.commit()
		finally:
			connection.close()

		self._delete_if_effectively_default_sync(excursion_id)

	def _delete_if_effectively_default_sync(self, excursion_id: str) -> None:
		override = self._get_excursion_override_sync(excursion_id)
		if override is None:
			return

		if (
			override.title is None
			and override.short_title is None
			and override.time is None
			and override.price is None
			and override.description is None
			and override.included is None
			and override.image_path is None
			and override.is_active
		):
			self._delete_excursion_override_sync(excursion_id)

	def _set_excursion_image_path_sync(self, excursion_id: str, image_path: str | None) -> None:
		self._upsert_excursion_override_sync(excursion_id, {IMAGE_PATH_FIELD: image_path})

	def _delete_excursion_override_sync(self, excursion_id: str) -> None:
		connection = self._connect()
		try:
			connection.execute("DELETE FROM excursion_overrides WHERE excursion_id = ?", (excursion_id,))
			connection.commit()
		finally:
			connection.close()
