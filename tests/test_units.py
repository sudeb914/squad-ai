"""Focused unit tests for parsing / normalization / numeric ranges."""
import unittest

from app.core import normalization as N
from app.core import numeric_range as NR
from app.core import question_parser as QP
from app.core.confidence import intent_compatible
from app.core.models import QuestionType


class TestNormalization(unittest.TestCase):
    def test_curly_and_prefix(self):
        self.assertEqual(N.normalize("A) It’s Fine!"), "it's fine")

    def test_strip_prefix(self):
        self.assertEqual(N.strip_option_prefix("1. Yes"), "Yes")
        self.assertEqual(N.strip_option_prefix("(a) No"), "No")


class TestNumericRange(unittest.TestCase):
    def test_parse_number(self):
        self.assertEqual(NR.parse_number("$50,000"), 50000.0)
        self.assertEqual(NR.parse_number("age 39 years"), 39.0)
        self.assertEqual(NR.parse_number("50k"), 50000.0)

    def test_bounds(self):
        self.assertTrue(NR.parse_bound("35+").contains(39))
        self.assertTrue(NR.parse_bound("35 or older").contains(35))
        self.assertFalse(NR.parse_bound("under 35").contains(35))
        self.assertTrue(NR.parse_bound("31-40").contains(39))
        self.assertFalse(NR.parse_bound("31-40").contains(41))

    def test_match_range_option_prefers_closed(self):
        idx, _ = NR.match_range_option(39, ["18+", "31-40", "50+"])
        self.assertEqual(idx, 1)

    def test_boolean_from_threshold(self):
        self.assertTrue(NR.answer_numeric_boolean(39, "are you 35 or older"))
        self.assertFalse(NR.answer_numeric_boolean(30, "are you 35 or older"))


class TestQuestionParser(unittest.TestCase):
    def test_boolean(self):
        q = QP.parse("Are you employed?")
        self.assertEqual(q.qtype, QuestionType.BOOLEAN)

    def test_numeric_range(self):
        q = QP.parse("Age?", ["18-24", "25-34", "35-44"])
        self.assertEqual(q.qtype, QuestionType.NUMERIC_RANGE)

    def test_single_choice(self):
        q = QP.parse("Favorite color?", ["Red", "Blue", "Green"])
        self.assertEqual(q.qtype, QuestionType.SINGLE_CHOICE)

    def test_options_from_markers(self):
        q = QP.parse("Pick one\nA) Red\nB) Blue\nC) Green")
        self.assertEqual(len(q.options), 3)
        self.assertEqual(q.options[0].original, "Red")

    def test_markerless_radio_options(self):
        # Real surveys: radio options on their own lines, no A/B/C markers,
        # with an instruction line that must be ignored.
        q = QP.parse("What is your age bracket?\n"
                     "Choose one of the following answers\n"
                     "18-24 years\n25-34 years\n35-44 years\n"
                     "45-54 years\n55 years or older\nNo answer")
        self.assertEqual(q.qtype, QuestionType.NUMERIC_RANGE)
        self.assertEqual(len(q.options), 6)
        self.assertEqual(q.options[0].original, "18-24 years")
        self.assertEqual(q.options[1].original, "25-34 years")


class TestIntent(unittest.TestCase):
    def test_own_vs_buy_incompatible(self):
        self.assertFalse(intent_compatible(
            "do you currently own a car", "do you plan to buy a car next year",
            [], []))

    def test_negation_incompatible(self):
        self.assertFalse(intent_compatible(
            "do you like coffee", "do you not like coffee", [], []))

    def test_same_intent_compatible(self):
        self.assertTrue(intent_compatible(
            "what is your favorite topping", "whats your favorite topping",
            [], []))


if __name__ == "__main__":
    unittest.main()
