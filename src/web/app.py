from __future__ import annotations

import html
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from aiogram import Bot
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from src.bot.config.settings import load_settings
from src.bot.services.bookings import BookingSubmissionData, booking_service
from src.bot.services.excursions import excursion_service


logger = logging.getLogger(__name__)
WEB_ROOT = Path(__file__).resolve().parent


class WebBookingRequest(BaseModel):
	excursion_id: str = Field(min_length=1, max_length=80)
	customer_name: str = Field(min_length=2, max_length=120)
	phone: str = Field(min_length=7, max_length=40)
	excursion_date: str = Field(min_length=10, max_length=10)
	people_count: int = Field(ge=1, le=50)

	@field_validator("customer_name", "phone")
	@classmethod
	def clean_text(cls, value: str) -> str:
		cleaned = " ".join(value.split())
		if not cleaned:
			raise ValueError("Поле не может быть пустым")
		return cleaned


@asynccontextmanager
async def lifespan(_: FastAPI):
	await booking_service.initialize_storage()
	await excursion_service.initialize()
	yield


app = FastAPI(
	title="TravelFlow • Asia Mix Travel",
	description="Демо-платформа бронирования экскурсий во Вьетнаме",
	version="1.0.0",
	docs_url=None,
	redoc_url=None,
	lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=WEB_ROOT / "static"), name="static")


def excursion_payload(excursion) -> dict:
	return {
		"id": excursion.id,
		"title": excursion.title,
		"short_title": excursion.short_title,
		"time": excursion.time,
		"price": excursion.price,
		"description": excursion.description,
		"included": list(excursion.included),
		"not_included": list(excursion.not_included or ()),
		"what_to_bring": list(excursion.what_to_bring or ()),
		"restrictions": list(excursion.restrictions or ()),
		"departure_point": excursion.departure_point,
		"audience": list(excursion.audience),
		"interests": list(excursion.interests),
		"formats": list(excursion.formats),
		"image_url": f"/static/images/excursions/{excursion.id}.webp",
		"source_image_url": f"/api/excursions/{excursion.id}/image",
	}


async def notify_manager(booking_id: int, booking: WebBookingRequest, excursion_title: str) -> bool:
	settings = load_settings()
	if settings.manager_chat_id is None:
		return False
	message = (
		"🌐 <b>Новая заявка с сайта TravelFlow</b>\n\n"
		f"Номер: <b>#{booking_id}</b>\n"
		f"Экскурсия: <b>{html.escape(excursion_title)}</b>\n"
		f"Имя: {html.escape(booking.customer_name)}\n"
		f"Телефон: <code>{html.escape(booking.phone)}</code>\n"
		f"Дата: {html.escape(booking.excursion_date)}\n"
		f"Гостей: {booking.people_count}"
	)
	bot = Bot(settings.bot_token)
	try:
		await bot.send_message(settings.manager_chat_id, message, parse_mode="HTML")
		return True
	except Exception:
		logger.exception("Failed to notify manager about web booking %s", booking_id)
		return False
	finally:
		await bot.session.close()


@app.get("/", include_in_schema=False)
async def home() -> FileResponse:
	return FileResponse(WEB_ROOT / "static" / "index.html")


@app.get("/health")
async def health() -> dict[str, str]:
	return {"status": "ok", "service": "travelflow-platform"}


@app.get("/api/excursions")
async def list_excursions() -> list[dict]:
	excursions = await excursion_service.list_effective_excursions()
	return [excursion_payload(item) for item in excursions]


@app.get("/api/excursions/{excursion_id}")
async def get_excursion(excursion_id: str) -> dict:
	excursion = await excursion_service.get_effective_excursion(excursion_id)
	if excursion is None or not excursion.is_active:
		raise HTTPException(status_code=404, detail="Экскурсия не найдена")
	return excursion_payload(excursion)


@app.get("/api/excursions/{excursion_id}/image", include_in_schema=False)
async def get_excursion_image(excursion_id: str) -> FileResponse:
	try:
		image_path, _ = await excursion_service.resolve_excursion_media(excursion_id)
	except ValueError as error:
		raise HTTPException(status_code=404, detail="Изображение не найдено") from error
	return FileResponse(image_path)


@app.post("/api/bookings", status_code=201)
async def create_booking(request: WebBookingRequest) -> dict:
	excursion = await excursion_service.get_effective_excursion(request.excursion_id)
	if excursion is None or not excursion.is_active:
		raise HTTPException(status_code=404, detail="Экскурсия недоступна")

	booking_id = await booking_service.save_booking(
		BookingSubmissionData(
			excursion_id=excursion.id,
			excursion_title=excursion.title,
			customer_name=request.customer_name,
			phone=request.phone,
			excursion_date=request.excursion_date,
			people_count=request.people_count,
			telegram_user_id=0,
			telegram_username=None,
			telegram_full_name=None,
			source="web_platform",
		)
	)
	manager_notified = await notify_manager(booking_id, request, excursion.title)
	return {
		"booking_id": booking_id,
		"status": "accepted",
		"manager_notified": manager_notified,
		"message": "Заявка принята. Менеджер свяжется с вами для подтверждения.",
	}
