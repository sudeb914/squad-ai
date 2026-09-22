"""Tests for splitting a multi-question OCR page into per-question blocks."""
import unittest

from app.core.question_splitter import split_questions


class TestSplit(unittest.TestCase):
    def test_single_question_returns_one_block(self):
        text = "Which age group are you in?\n18-24\n25-34\n35-44\n45+"
        blocks = split_questions(text)
        self.assertEqual(len(blocks), 1)
        self.assertIn("age group", blocks[0])

    def test_two_questions_split_with_their_options(self):
        text = (
            "Which age group are you in?\n"
            "18-24\n25-34\n35-44\n45+\n"
            "What is your employment status?\n"
            "Full-time\nPart-time\nRetired\n"
        )
        blocks = split_questions(text)
        self.assertEqual(len(blocks), 2)
        self.assertIn("age group", blocks[0])
        self.assertIn("18-24", blocks[0])
        self.assertIn("45+", blocks[0])
        self.assertNotIn("employment", blocks[0])
        self.assertIn("employment status", blocks[1])
        self.assertIn("Full-time", blocks[1])
        self.assertIn("Retired", blocks[1])

    def test_multiline_question_text_stays_together(self):
        text = (
            "In your honest opinion,\n"
            "how satisfied are you with the service?\n"
            "Very satisfied\nSatisfied\nUnhappy\n"
            "Would you recommend us to a friend?\n"
            "Yes\nNo\n"
        )
        blocks = split_questions(text)
        self.assertEqual(len(blocks), 2)
        self.assertIn("honest opinion", blocks[0])
        self.assertIn("how satisfied", blocks[0])
        self.assertIn("Very satisfied", blocks[0])
        self.assertNotIn("recommend", blocks[0])
        self.assertIn("recommend us", blocks[1])
        self.assertIn("Yes", blocks[1])

    def test_no_question_mark_is_single_block(self):
        text = "Select your favourite colour\nRed\nBlue\nGreen"
        self.assertEqual(len(split_questions(text)), 1)

    def test_empty(self):
        self.assertEqual(split_questions(""), [])


if __name__ == "__main__":
    unittest.main()
