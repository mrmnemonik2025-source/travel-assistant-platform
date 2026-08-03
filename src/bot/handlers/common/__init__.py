from aiogram import Router

from src.bot.handlers.admin import router as admin_router
from src.bot.handlers.common.booking import router as booking_router
from src.bot.handlers.common.catalog import router as catalog_router
from src.bot.handlers.common.company import router as company_router
from src.bot.handlers.common.manager_contact import router as manager_contact_router
from src.bot.handlers.common.selection import router as selection_router
from src.bot.handlers.common.start import router as start_router


router = Router(name="common")
router.include_router(admin_router)
router.include_router(start_router)
router.include_router(company_router)
router.include_router(catalog_router)
router.include_router(selection_router)
router.include_router(manager_contact_router)
router.include_router(booking_router)


__all__ = ["router"]
