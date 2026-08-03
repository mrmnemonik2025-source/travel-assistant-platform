from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from src.bot.config.settings import load_settings, parse_admin_user_ids


class SettingsTests(unittest.TestCase):
	def test_parse_admin_user_ids(self) -> None:
		self.assertEqual(frozenset({10, 20}), parse_admin_user_ids("10, 20,10"))

	def test_reject_non_integer_admin_user_id(self) -> None:
		with self.assertRaisesRegex(RuntimeError, "ADMIN_USER_IDS"):
			parse_admin_user_ids("10,unknown")

	def test_require_bot_token(self) -> None:
		with patch.dict(os.environ, {}, clear=True):
			with self.assertRaisesRegex(RuntimeError, "BOT_TOKEN"):
				load_settings()

	def test_reject_invalid_manager_chat_id(self) -> None:
		with patch.dict(os.environ, {"BOT_TOKEN": "test", "MANAGER_CHAT_ID": "manager"}, clear=True):
			with self.assertRaisesRegex(RuntimeError, "MANAGER_CHAT_ID"):
				load_settings()

	def test_load_complete_settings(self) -> None:
		environment = {
			"BOT_TOKEN": "test",
			"MANAGER_CHAT_ID": "-100123",
			"ADMIN_USER_IDS": "10,20",
			"LOG_LEVEL": "DEBUG",
		}
		with patch.dict(os.environ, environment, clear=True):
			settings = load_settings()

		self.assertEqual("test", settings.bot_token)
		self.assertEqual(-100123, settings.manager_chat_id)
		self.assertEqual(frozenset({10, 20}), settings.admin_user_ids)
		self.assertEqual("DEBUG", settings.log_level)
