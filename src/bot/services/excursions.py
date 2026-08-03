from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path

from src.bot.data.excursions import ALL_EXCURSIONS, EXCURSIONS_BY_ID, ExcursionData
from src.bot.repositories.excursions import EDITABLE_FIELDS, ExcursionOverrideRepository, ExcursionOverrideRow


logger = logging.getLogger(__name__)

BOT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[3]
PLACEHOLDER_IMAGE_PATH = BOT_ROOT / "data" / "images" / "excursions" / "placeholder.png"
MEDIA_ROOT = PROJECT_ROOT / "data" / "media" / "excursions"
ALLOWED_IMAGE_EXTENSIONS: set[str] = {".jpg", ".jpeg", ".png", ".webp"}


class ExcursionService:
	def __init__(self, repository: ExcursionOverrideRepository | None = None) -> None:
		self.repository = repository or ExcursionOverrideRepository()
		self.project_root = PROJECT_ROOT
		self.media_root = MEDIA_ROOT
		self.placeholder_image_path = PLACEHOLDER_IMAGE_PATH

	async def initialize(self) -> None:
		try:
			await self.repository.initialize()
		except Exception:
			logger.exception("Failed to initialize excursion overrides repository")

	def is_known_excursion_id(self, excursion_id: str) -> bool:
		return excursion_id in EXCURSIONS_BY_ID

	def ensure_known_excursion_id(self, excursion_id: str) -> None:
		if not self.is_known_excursion_id(excursion_id):
			raise ValueError(f"Unknown excursion id: {excursion_id}")

	def _resolve_path_from_project(self, path_value: str) -> Path:
		candidate = Path(path_value)
		if not candidate.is_absolute():
			candidate = self.project_root / candidate
		return candidate.resolve()

	def _resolve_custom_media_path(self, relative_path: str) -> Path | None:
		try:
			candidate = self._resolve_path_from_project(relative_path)
		except Exception:
			return None

		media_root = self.media_root.resolve()
		try:
			candidate.relative_to(media_root)
		except ValueError:
			return None
		return candidate

	def _resolve_effective_media(self, base: ExcursionData, override: ExcursionOverrideRow | None) -> tuple[Path, str]:
		if override and override.image_path:
			override_path = self._resolve_custom_media_path(override.image_path)
			if override_path is None:
				logger.warning(
					"Unsafe override image path for excursion '%s': %s. Falling back.",
					base.id,
					override.image_path,
				)
			elif override_path.exists():
				return override_path, "override"
			else:
				logger.warning(
					"Override image path does not exist for excursion '%s': %s. Falling back.",
					base.id,
					override_path,
				)

		if base.image_path:
			base_path = self._resolve_path_from_project(base.image_path)
			if base_path.exists():
				return base_path, "base"
			logger.warning(
				"Base image path does not exist for excursion '%s': %s. Using placeholder.",
				base.id,
				base_path,
			)

		return self.placeholder_image_path, "placeholder"

	def _build_effective_image_path(self, base: ExcursionData, override: ExcursionOverrideRow | None) -> str | None:
		_, source = self._resolve_effective_media(base, override)
		if source == "override" and override is not None:
			return override.image_path
		if source == "base":
			return base.image_path
		return None

	def _apply_override(self, base: ExcursionData, override: ExcursionOverrideRow | None) -> ExcursionData:
		if override is None:
			return base
		included_value = base.included
		if override.included is not None:
			included_value = tuple(line.strip() for line in override.included.splitlines() if line.strip())
		effective_image_path = self._build_effective_image_path(base, override)
		return replace(
			base,
			title=override.title if override.title is not None else base.title,
			short_title=override.short_title if override.short_title is not None else base.short_title,
			time=override.time if override.time is not None else base.time,
			price=override.price if override.price is not None else base.price,
			description=override.description if override.description is not None else base.description,
			included=included_value,
			image_path=effective_image_path,
			is_active=override.is_active,
		)

	async def get_effective_excursion(self, excursion_id: str) -> ExcursionData | None:
		base = EXCURSIONS_BY_ID.get(excursion_id)
		if base is None:
			return None
		try:
			override = await self.repository.get_excursion_override(excursion_id)
		except Exception:
			logger.exception("Failed to get excursion override for %s", excursion_id)
			return base
		return self._apply_override(base, override)

	async def list_effective_excursions(self, *, include_inactive: bool = False) -> list[ExcursionData]:
		bases = list(ALL_EXCURSIONS)
		try:
			overrides = {row.excursion_id: row for row in await self.repository.list_excursion_overrides()}
		except Exception:
			logger.exception("Failed to list excursion overrides")
			if include_inactive:
				return bases
			return [item for item in bases if item.is_active]

		result: list[ExcursionData] = []
		for base in bases:
			effective = self._apply_override(base, overrides.get(base.id))
			if include_inactive or effective.is_active:
				result.append(effective)
		return result

	async def update_excursion_field(self, excursion_id: str, field_name: str, value: str) -> None:
		self.ensure_known_excursion_id(excursion_id)
		if field_name not in EDITABLE_FIELDS:
			raise ValueError(f"Unsupported excursion field: {field_name}")
		await self.repository.upsert_excursion_override(excursion_id, {field_name: value})

	async def reset_excursion_field(self, excursion_id: str, field_name: str) -> None:
		self.ensure_known_excursion_id(excursion_id)
		await self.repository.reset_excursion_field(excursion_id, field_name)

	async def set_excursion_active(self, excursion_id: str, is_active: bool) -> None:
		self.ensure_known_excursion_id(excursion_id)
		await self.repository.set_excursion_active(excursion_id, is_active)

	def normalize_image_extension(self, extension: str | None) -> str:
		clean = (extension or "").strip().lower()
		if not clean:
			clean = ".jpg"
		if not clean.startswith("."):
			clean = f".{clean}"
		if clean not in ALLOWED_IMAGE_EXTENSIONS:
			raise ValueError(f"Unsupported image extension: {clean}")
		return clean

	def build_excursion_media_relative_path(self, excursion_id: str, extension: str) -> Path:
		self.ensure_known_excursion_id(excursion_id)
		safe_extension = self.normalize_image_extension(extension)
		relative = Path("data") / "media" / "excursions" / excursion_id / f"current{safe_extension}"
		resolved = (self.project_root / relative).resolve()
		media_root = self.media_root.resolve()
		resolved.relative_to(media_root)
		return relative

	def ensure_excursion_media_dir(self, excursion_id: str) -> Path:
		self.ensure_known_excursion_id(excursion_id)
		directory = self.media_root / excursion_id
		directory.mkdir(parents=True, exist_ok=True)
		return directory

	async def resolve_excursion_media(self, excursion_id: str) -> tuple[Path, str]:
		base = EXCURSIONS_BY_ID.get(excursion_id)
		if base is None:
			raise ValueError(f"Unknown excursion id: {excursion_id}")
		try:
			override = await self.repository.get_excursion_override(excursion_id)
		except Exception:
			logger.exception("Failed to read override for excursion media %s", excursion_id)
			override = None
		return self._resolve_effective_media(base, override)

	async def get_excursion_image_source(self, excursion_id: str) -> str:
		_, source = await self.resolve_excursion_media(excursion_id)
		return source

	def resolve_media_path_for_excursion(self, excursion: ExcursionData) -> Path:
		if excursion.image_path:
			candidate = self._resolve_path_from_project(excursion.image_path)
			if candidate.exists():
				return candidate
			logger.warning(
				"Effective image path does not exist for excursion '%s': %s. Using placeholder.",
				excursion.id,
				candidate,
			)
		return self.placeholder_image_path

	def remove_custom_image_file(self, stored_path: str | None) -> None:
		if not stored_path:
			return
		resolved = self._resolve_custom_media_path(stored_path)
		if resolved is None:
			logger.warning("Skip deleting unsafe custom image path: %s", stored_path)
			return

		try:
			if resolved.exists():
				resolved.unlink()
		except Exception:
			logger.exception("Failed to delete custom image file: %s", resolved)
			return

		media_root = self.media_root.resolve()
		parent = resolved.parent
		while parent != media_root:
			try:
				parent.rmdir()
			except OSError:
				break
			parent = parent.parent

	async def set_excursion_image_path(self, excursion_id: str, image_path: str) -> None:
		self.ensure_known_excursion_id(excursion_id)
		resolved = self._resolve_custom_media_path(image_path)
		if resolved is None:
			raise ValueError(f"Unsafe image path: {image_path}")
		await self.repository.set_excursion_image_path(excursion_id, image_path)

	async def reset_excursion_image_path(self, excursion_id: str) -> None:
		self.ensure_known_excursion_id(excursion_id)
		override = await self.repository.get_excursion_override(excursion_id)
		await self.repository.reset_excursion_image_path(excursion_id)
		self.remove_custom_image_file(override.image_path if override else None)

	async def clear_excursion_override(self, excursion_id: str) -> None:
		self.ensure_known_excursion_id(excursion_id)
		override = await self.repository.get_excursion_override(excursion_id)
		await self.repository.delete_excursion_override(excursion_id)
		self.remove_custom_image_file(override.image_path if override else None)


excursion_service = ExcursionService()
