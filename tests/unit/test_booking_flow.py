"""Regression tests for booking flow fixes:
1. Booking from main menu now requires excursion selection (Bug 1).
2. Cancel handler is registered before step handlers (Bug 2).
3. Phone formatting (Item 3).
4. Selection scoring improvement (Item 9).
"""
from __future__ import annotations

import unittest

from src.bot.handlers.common.booking import (
    cancel_booking_in_state,
    format_phone_display,
    handle_date,
    handle_excursion_selection,
    handle_name,
    handle_people,
    handle_phone_contact,
    handle_phone_text,
    router,
    start_booking_from_menu,
)
from src.bot.handlers.common.selection import calculate_score
from src.bot.data.excursions import ASIA_MIX_ISLANDS, NIGHT_CRUISE, NORTHERN_ISLANDS


class PhoneFormatTests(unittest.TestCase):
    def test_russian_plus7_format(self) -> None:
        self.assertEqual("+7 928 234 25 03", format_phone_display("+79282342503"))

    def test_russian_7_without_plus(self) -> None:
        self.assertEqual("+7 928 234 25 03", format_phone_display("79282342503"))

    def test_international_non_russian_unchanged(self) -> None:
        self.assertEqual("+84901234567", format_phone_display("+84901234567"))

    def test_short_number_unchanged(self) -> None:
        self.assertEqual("89991234567", format_phone_display("89991234567"))

    def test_already_formatted_unchanged(self) -> None:
        # already formatted correctly → doesn't match +7XXXXXXXXXX so returned as-is
        self.assertEqual("+7 999 123 45 67", format_phone_display("+7 999 123 45 67"))

    def test_leading_trailing_spaces_stripped(self) -> None:
        self.assertEqual("+7 928 234 25 03", format_phone_display("  +79282342503  "))


class BookingCancelHandlerOrderTests(unittest.TestCase):
    """Verify cancel_booking_in_state is registered BEFORE step handlers in booking router."""

    def _message_handler_names(self) -> list[str]:
        return [handler.callback.__name__ for handler in router.message.handlers]

    def test_cancel_registered_before_handle_name(self) -> None:
        names = self._message_handler_names()
        cancel_idx = names.index("cancel_booking_in_state")
        name_idx = names.index("handle_name")
        self.assertLess(cancel_idx, name_idx, "cancel must fire before handle_name")

    def test_cancel_registered_before_handle_date(self) -> None:
        names = self._message_handler_names()
        cancel_idx = names.index("cancel_booking_in_state")
        date_idx = names.index("handle_date")
        self.assertLess(cancel_idx, date_idx, "cancel must fire before handle_date")

    def test_cancel_registered_before_handle_people(self) -> None:
        names = self._message_handler_names()
        cancel_idx = names.index("cancel_booking_in_state")
        people_idx = names.index("handle_people")
        self.assertLess(cancel_idx, people_idx, "cancel must fire before handle_people")

    def test_cancel_registered_before_handle_phone_text(self) -> None:
        names = self._message_handler_names()
        cancel_idx = names.index("cancel_booking_in_state")
        phone_idx = names.index("handle_phone_text")
        self.assertLess(cancel_idx, phone_idx, "cancel must fire before handle_phone_text")


class BookingMenuExcursionSelectionTests(unittest.TestCase):
    """start_booking_from_menu must NOT go directly to waiting_for_name."""

    def test_start_booking_from_menu_is_registered(self) -> None:
        names = [h.callback.__name__ for h in router.message.handlers]
        self.assertIn("start_booking_from_menu", names)

    def test_handle_excursion_selection_is_registered_as_callback(self) -> None:
        names = [h.callback.__name__ for h in router.callback_query.handlers]
        self.assertIn("handle_excursion_selection", names)


class SelectionScoringTests(unittest.TestCase):
    """Asia Mix Islands and Northern Islands should outscore Night Cruise for family/beach/calm."""

    def test_family_beach_calm_asia_mix_higher_than_night_cruise(self) -> None:
        score_asia = calculate_score(
            ASIA_MIX_ISLANDS,
            audience="Семья",
            interest="Острова и пляжи",
            trip_format="Спокойный отдых",
        )
        score_night = calculate_score(
            NIGHT_CRUISE,
            audience="Семья",
            interest="Острова и пляжи",
            trip_format="Спокойный отдых",
        )
        self.assertGreater(score_asia, score_night)

    def test_family_beach_calm_northern_higher_than_night_cruise(self) -> None:
        score_north = calculate_score(
            NORTHERN_ISLANDS,
            audience="Семья",
            interest="Острова и пляжи",
            trip_format="Спокойный отдых",
        )
        score_night = calculate_score(
            NIGHT_CRUISE,
            audience="Семья",
            interest="Острова и пляжи",
            trip_format="Спокойный отдых",
        )
        self.assertGreater(score_north, score_night)

    def test_night_cruise_still_relevant_for_couple_evening_calm(self) -> None:
        score = calculate_score(
            NIGHT_CRUISE,
            audience="Пара",
            interest="Вечерняя программа",
            trip_format="Спокойный отдых",
        )
        self.assertEqual(3, score)


if __name__ == "__main__":
    unittest.main()
