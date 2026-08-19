import logging
import re
from html import escape

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.formatting import Bold, Code, Text

from src.bot.config.settings import load_settings
from src.bot.keyboards.inline import ABOUT_CONTACT_MANAGER_CALLBACK
from src.bot.keyboards.reply import (
    CANCEL_MANAGER_MESSAGE_TEXT,
    main_menu_keyboard,
    manager_contact_keyboard,
)
from src.bot.states.manager_contact import ManagerContactStates


router = Router(name="common_manager_contact")
logger = logging.getLogger(__name__)
CLIENT_ID_PATTERN = re.compile(r"\bUser ID\b\s*(?::\s*)?(\d+)", re.IGNORECASE)
MANAGER_REPLY_CALLBACK_PREFIX = "manager:reply:"
MANAGER_REPLY_CLIENT_ID_KEY = "manager_reply_client_id"


def build_contact_intro_text() -> str:
    return Text(
        "💬 ",
        Bold("Связь с менеджером"),
        "\n\n",
        "Напишите ваш вопрос одним сообщением.\n",
        "Менеджер получит его вместе с вашими Telegram-данными.",
    ).as_html()


def build_manager_forward_text(message: Message, text: str) -> str:
    full_name = (message.from_user.full_name if message.from_user else "Не указано").strip() or "Не указано"
    username = f"@{message.from_user.username}" if message.from_user and message.from_user.username else "не указан"
    user_id = message.from_user.id if message.from_user else message.chat.id

    return Text(
        "🆕 ",
        Bold("Обращение к менеджеру"),
        "\n\n",
        "👤 ",
        Bold("Имя"),
        "\n",
        escape(full_name),
        "\n\n",
        "🔖 ",
        Bold("Username"),
        "\n",
        escape(username),
        "\n\n",
        "🆔 ",
        Bold("User ID"),
        "\n",
        Code(str(user_id)),
        "\n\n",
        "💬 ",
        Bold("Текст обращения"),
        "\n",
        escape(text),
    ).as_html()


def extract_client_id_from_text(text: str) -> int | None:
    match = CLIENT_ID_PATTERN.search(text)
    if not match:
        return None
    return int(match.group(1))


def extract_client_id(message: Message | None) -> int | None:
    if message is None:
        return None

    message_text = message.text or message.caption or ""
    return extract_client_id_from_text(message_text)


def build_manager_contact_card_keyboard(*, client_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Ответить клиенту",
                    callback_data=f"{MANAGER_REPLY_CALLBACK_PREFIX}{client_id}",
                ),
            ],
        ]
    )


def extract_client_id_from_callback_data(callback_data: str | None) -> int | None:
    if not callback_data:
        return None

    if not callback_data.startswith(MANAGER_REPLY_CALLBACK_PREFIX):
        return None

    client_id_raw = callback_data[len(MANAGER_REPLY_CALLBACK_PREFIX) :]
    if not client_id_raw.isdigit():
        return None

    return int(client_id_raw)


class ManagerReplyToClientFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        settings = load_settings()
        if settings.manager_chat_id is None or message.chat.id != settings.manager_chat_id:
            return False

        if not message.reply_to_message or not message.text:
            return False

        return extract_client_id(message.reply_to_message) is not None


async def start_manager_contact(message: Message, state: FSMContext) -> None:
    
    settings = load_settings()
    if settings.manager_chat_id is None:
        logger.warning("MANAGER_CHAT_ID is not set, manager contact is unavailable")
        await message.answer(
            "Связь с менеджером временно недоступна. Попробуйте позже.",
            reply_markup=main_menu_keyboard,
        )
        return

    await state.clear()
    await state.set_state(ManagerContactStates.waiting_for_manager_message)
    await message.answer(
        build_contact_intro_text(),
        parse_mode=ParseMode.HTML,
        reply_markup=manager_contact_keyboard,
    )


@router.message(F.text == "💬 Связаться с менеджером")
async def start_manager_contact_from_menu(message: Message, state: FSMContext) -> None:
    await start_manager_contact(message, state)


@router.callback_query(F.data == ABOUT_CONTACT_MANAGER_CALLBACK)
async def start_manager_contact_from_inline(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message:
        await start_manager_contact(callback.message, state)
    await callback.answer()


@router.callback_query(F.data.startswith(MANAGER_REPLY_CALLBACK_PREFIX))
async def prepare_reply_to_client_from_button(callback: CallbackQuery, state: FSMContext) -> None:
    settings = load_settings()
    if settings.manager_chat_id is None:
        return

    if callback.message is None or callback.message.chat.id != settings.manager_chat_id:
        return

    client_id = extract_client_id_from_callback_data(callback.data)
    if client_id is None:
        await callback.answer("Не удалось определить клиента.", show_alert=True)
        logger.error("Failed to determine client_id for manager reply from callback data: %r", callback.data)
        return

    await state.update_data(**{MANAGER_REPLY_CLIENT_ID_KEY: client_id})
    await state.set_state(ManagerContactStates.waiting_for_client_reply)
    await callback.message.answer(f"Введите ответ клиенту одним сообщением. User ID: {client_id}")
    await callback.answer()


@router.message(ManagerReplyToClientFilter())
async def reply_to_client_from_manager(message: Message, state: FSMContext) -> None:
    client_id = extract_client_id(message.reply_to_message)
    if client_id is None:
        await message.reply("Не удалось определить клиента в исходном сообщении.")
        return

    await state.update_data(**{MANAGER_REPLY_CLIENT_ID_KEY: client_id})
    await state.set_state(ManagerContactStates.waiting_for_client_reply)
    await message.reply(f"Введите ответ клиенту одним сообщением. User ID: {client_id}")


@router.message(ManagerContactStates.waiting_for_client_reply, F.text)
async def send_client_reply_from_manager(message: Message, state: FSMContext) -> None:
    settings = load_settings()
    if settings.manager_chat_id is None or message.chat.id != settings.manager_chat_id:
        await state.clear()
        return

    data = await state.get_data()
    client_id_raw = data.get(MANAGER_REPLY_CLIENT_ID_KEY)

    try:
        client_id = int(client_id_raw)
    except (TypeError, ValueError):
        logger.error("Manager reply state is missing valid client_id: %r", client_id_raw)
        await message.reply("Не удалось определить получателя. Нажмите «Ответить клиенту» ещё раз.")
        await state.clear()
        return

    try:
        await message.bot.send_message(
            chat_id=client_id,
            text=message.text,
        )
    except Exception:
        logger.exception("Failed to send manager reply to client %s", client_id)
        await message.reply("Не удалось отправить ответ клиенту. Попробуйте ещё раз.")
        await state.clear()
        return

    await state.clear()
    await message.reply("✅ Ответ отправлен клиенту.")


@router.message(ManagerContactStates.waiting_for_manager_message, F.text == CANCEL_MANAGER_MESSAGE_TEXT)
async def cancel_manager_contact(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Сообщение менеджеру отменено. Вы вернулись в главное меню.",
        reply_markup=main_menu_keyboard,
    )


@router.message(ManagerContactStates.waiting_for_manager_message)
async def handle_manager_message(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer(
            "Отправьте вопрос текстовым сообщением одним сообщением.",
            reply_markup=manager_contact_keyboard,
        )
        return

    if text.startswith("/"):
        await message.answer(
            "Пожалуйста, отправьте вопрос обычным текстом без команды.",
            reply_markup=manager_contact_keyboard,
        )
        return

    settings = load_settings()
    if settings.manager_chat_id is None:
        logger.warning("MANAGER_CHAT_ID is not set while sending manager contact message")
        await state.clear()
        await message.answer(
            "Связь с менеджером временно недоступна. Попробуйте позже.",
            reply_markup=main_menu_keyboard,
        )
        return

    try:
        await message.bot.send_message(
            chat_id=settings.manager_chat_id,
            text=build_manager_forward_text(message, text),
            parse_mode=ParseMode.HTML,
            reply_markup=build_manager_contact_card_keyboard(client_id=message.from_user.id if message.from_user else message.chat.id),
        )
    except Exception:
        logger.exception("Failed to send manager contact message")
        await message.answer(
            "Не удалось отправить сообщение менеджеру. Попробуйте немного позже.",
            reply_markup=main_menu_keyboard,
        )
        await state.clear()
        return

    await state.clear()
    await message.answer(
        "✅ Сообщение отправлено менеджеру. Мы скоро с вами свяжемся.",
        reply_markup=main_menu_keyboard,
    )
