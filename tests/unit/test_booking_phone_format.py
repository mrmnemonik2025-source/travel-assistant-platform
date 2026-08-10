from __future__ import annotations

import unittest

from src.bot.handlers.common.booking import format_phone_for_display


class BookingPhoneFormatTests(unittest.TestCase):
	def test_formats_ru_phone_with_plus_seven(self) -> None:
		self.assertEqual("+7 (928) 234-25-03", format_phone_for_display("+79282342503"))

	def test_formats_ru_phone_with_leading_eight(self) -> None:
		self.assertEqual("+7 (928) 234-25-03", format_phone_for_display("89282342503"))

	def test_formats_ru_phone_without_country_code(self) -> None:
		self.assertEqual("+7 (928) 234-25-03", format_phone_for_display("9282342503"))

	def test_keeps_unrecognized_phone_as_is(self) -> None:
		self.assertEqual("123", format_phone_for_display("123"))
