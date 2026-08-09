from __future__ import annotations

import unittest

from src.bot.handlers.common.manager_contact import extract_client_id_from_text


class ManagerContactTests(unittest.TestCase):
    def test_extract_client_id_from_contact_message(self) -> None:
        text = (
            "🆕 Обращение к менеджеру\n\n"
            "👤 Имя\nИван Петров\n\n"
            "🔖 Username\n@ivan\n\n"
            "🆔 User ID\n123456789\n\n"
            "💬 Текст обращения\nХочу уточнить детали экскурсии"
        )

        self.assertEqual(123456789, extract_client_id_from_text(text))

    def test_extract_client_id_from_booking_message(self) -> None:
        text = (
            "🆕 Новая заявка\n\n"
            "🆔 Заявка №\n42\n\n"
            "Telegram\n"
            "Username: @ivan\n"
            "User ID: 987654321"
        )

        self.assertEqual(987654321, extract_client_id_from_text(text))

    def test_extract_client_id_returns_none_when_missing(self) -> None:
        self.assertIsNone(extract_client_id_from_text("Сообщение без идентификатора"))