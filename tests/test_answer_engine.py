"""End-to-end answer-engine tests (spec §39).

Explicitly verifies that locally solvable questions trigger ZERO API calls and
that an unresolved question triggers at most ONE.
"""
import unittest

from tests.conftest_helpers import make_services
from app.core.models import AnswerSource


class TestLocalDeterministic(unittest.TestCase):
    def setUp(self):
        self.svc, self.fake = make_services({
            "age": "39",
            "state": "California",
            "employment_status": "Full-time employed",
            "household_size": "4",
            "income": "62000",
        })

    def test_exact_profile_fact(self):
        r = self.svc.engine.answer("What is your age?")
        self.assertEqual(r.answer, "39")
        self.assertEqual(r.source, AnswerSource.LOCAL_FACT)
        self.assertEqual(self.fake.calls, 0)

    def test_numeric_age_range(self):
        r = self.svc.engine.answer(
            "Which age range applies to you?",
            explicit_options=["18-24", "25-34", "35-44", "45+"])
        self.assertEqual(r.selected_option, "35-44")
        self.assertEqual(r.source, AnswerSource.LOCAL_RULE)
        self.assertEqual(r.reasoning_code, "NUMERIC_RANGE_MATCH")
        self.assertEqual(self.fake.calls, 0)

    def test_income_range(self):
        r = self.svc.engine.answer(
            "Which income range includes your household income?",
            explicit_options=["Under $25,000", "$25,000-$49,999",
                              "$50,000-$74,999", "$75,000+"])
        self.assertEqual(r.selected_option, "$50,000-$74,999")
        self.assertEqual(self.fake.calls, 0)

    def test_yes_no_comparison(self):
        r = self.svc.engine.answer("Are you 35 years old or older?")
        self.assertIn(r.answer.lower(), ("yes", "true"))
        self.assertEqual(self.fake.calls, 0)

    def test_yes_no_comparison_false(self):
        r = self.svc.engine.answer("Are you 45 years old or older?")
        self.assertIn(r.answer.lower(), ("no", "false"))
        self.assertEqual(self.fake.calls, 0)

    def test_same_field_different_phrasings(self):
        # Different wordings, same profile answer, all local & free.
        for q in ["What is your age?", "Select your age.", "Your age is",
                  "Age?", "Please enter your age", "How old are you?"]:
            r = self.svc.engine.answer(q)
            self.assertEqual(r.answer, "39", f"failed on: {q}")
            self.assertTrue(r.source.is_free, f"used API on: {q}")
        self.assertEqual(self.fake.calls, 0)

    def test_subjective_not_answered_from_bare_fact(self):
        # "favorite" must NOT be answered from a plain profile field.
        self.svc.profile.upsert("color", "blue")
        r = self.svc.engine.answer("What is your favorite color?")
        self.assertNotEqual(r.reasoning_code, "PROFILE_VALUE_PROMPT")

    def test_age_boolean_without_the_word_age(self):
        # "older"/"younger" imply age even when the word "age" is absent.
        r1 = self.svc.engine.answer("Are you 30 or older?")
        self.assertIn(r1.answer.lower(), ("yes", "true"))
        self.assertEqual(self.fake.calls, 0)
        r2 = self.svc.engine.answer("Are you younger than 50?")
        self.assertIn(r2.answer.lower(), ("yes", "true"))
        r3 = self.svc.engine.answer("Are you 45 or older?")
        self.assertIn(r3.answer.lower(), ("no", "false"))
        self.assertEqual(self.fake.calls, 0)

    def test_employment_option_mapping(self):
        r = self.svc.engine.answer(
            "Which best describes your employment?",
            explicit_options=["Working full time", "Working part time",
                              "Not employed", "Retired"])
        self.assertEqual(r.selected_option, "Working full time")
        self.assertTrue(r.source.is_free)
        self.assertEqual(self.fake.calls, 0)

    def test_markerless_age_bracket(self):
        # Radio-button bracket (no A/B/C) with age 39 -> "35-44 years", free.
        text = ("What is your age bracket?\nChoose one of the following\n"
                "18-24 years\n25-34 years\n35-44 years\n45-54 years\n"
                "55 years or older")
        r = self.svc.engine.answer(text)
        self.assertEqual(r.selected_option, "35-44 years")
        self.assertEqual(r.source, AnswerSource.LOCAL_RULE)
        self.assertEqual(self.fake.calls, 0)

    def test_ocr_prefix_artifacts(self):
        # Simulated OCR block with option markers and curly text.
        text = ("Which age range applies to you?\n"
                "A) 18-24\nB) 25-34\nC) 35-44\nD) 45+")
        r = self.svc.engine.answer(text)
        self.assertEqual(r.selected_option, "35-44")
        self.assertEqual(self.fake.calls, 0)


class TestMemory(unittest.TestCase):
    """Answer-memory was removed by request. These guard that it never comes
    back: an identical/similar question is answered fresh every time and is
    never served from a cached memory source."""

    def setUp(self):
        self.svc, self.fake = make_services({"age": "39"})

    def test_identical_question_not_reused_from_memory(self):
        q = "What is your favorite color for a new car?"
        r1 = self.svc.engine.answer(q)
        self.assertEqual(r1.source, AnswerSource.DEEPSEEK)
        self.assertEqual(self.fake.calls, 1)
        # Asking again must call the AI again — nothing is cached/reused.
        r2 = self.svc.engine.answer(q)
        self.assertEqual(r2.source, AnswerSource.DEEPSEEK)
        self.assertEqual(self.fake.calls, 2)

    def test_no_memory_sources_ever_returned(self):
        self.svc.engine.answer("What is your favorite pizza topping?")
        r = self.svc.engine.answer("what's your favorite pizza topping")
        self.assertNotIn(r.source, (AnswerSource.EXACT_MEMORY,
                                    AnswerSource.FUZZY_MEMORY,
                                    AnswerSource.SEMANTIC_MEMORY))
        self.assertEqual(self.fake.calls, 2)  # each answered fresh

    def test_nothing_stored_to_memory_repo(self):
        self.svc.engine.answer("Describe your ideal weekend.")
        # No answer is ever written to the memory store.
        self.assertEqual(self.svc.memory_repo.count(), 0)


class TestApiDiscipline(unittest.TestCase):
    def test_api_fallback_decision_and_single_call(self):
        svc, fake = make_services({"age": "39"})
        r = svc.engine.answer("Describe your ideal weekend getaway.")
        self.assertEqual(r.source, AnswerSource.DEEPSEEK)
        self.assertEqual(fake.calls, 1)  # exactly one call, no retry loop

    def test_local_question_never_calls_api(self):
        svc, fake = make_services({"age": "39"})
        for _ in range(5):
            svc.engine.answer("What is your age?")
        self.assertEqual(fake.calls, 0)

    def test_identity_fact_skips_api(self):
        # "What is my email?" with no profile match must NOT call DeepSeek
        # (it can't know) — saves cost and answers instantly.
        svc, fake = make_services({"age": "39"})
        r = svc.engine.answer("What is my email address?")
        self.assertEqual(r.source, AnswerSource.UNRESOLVED)
        self.assertEqual(r.reasoning_code, "NO_CONTEXT_SKIP_API")
        self.assertEqual(fake.calls, 0)

    def test_subjective_question_still_uses_api(self):
        # A subjective survey question with no local answer legitimately uses AI.
        svc, fake = make_services({"age": "39"})
        r = svc.engine.answer("What is your favorite weekend hobby?")
        self.assertEqual(r.source, AnswerSource.DEEPSEEK)
        self.assertEqual(fake.calls, 1)

    def test_no_api_when_disallowed(self):
        svc, fake = make_services({"age": "39"})
        r = svc.engine.answer("Tell me a story.", allow_api=False)
        self.assertEqual(r.source, AnswerSource.UNRESOLVED)
        self.assertEqual(fake.calls, 0)

    def test_answer_snaps_into_given_options(self):
        # If the model returns something not in the option list, the final
        # answer must still be one of the real options (never invented).
        from app.providers.base_provider import BaseAIProvider, ProviderResponse

        class Bad(BaseAIProvider):
            name = "deepseek"
            model = "fake"

            def answer(self, r):
                return ProviderResponse(answer="Best", selected_option_index=None,
                                        confidence=0.9, raw_text="{}",
                                        input_tokens=10, output_tokens=2)

            def test_connection(self):
                return True, "ok"

            def estimate_cost(self, i, o, c=0):
                return 0.0

        svc, _ = make_services({"age": "39"})
        svc.engine.provider_factory = lambda: Bad()
        r = svc.engine.answer("Rate it", explicit_options=["Poor", "Good",
                                                            "Very good"])
        self.assertIn(r.answer, ["Poor", "Good", "Very good"])

    def test_usage_logged(self):
        svc, fake = make_services({"age": "39"})
        svc.engine.answer("Describe your ideal vacation.")
        summary = svc.usage.summary()
        self.assertEqual(summary["calls"], 1)
        self.assertEqual(summary["input_tokens"], 120)


class TestReference(unittest.TestCase):
    def test_reference_qa_answered_free(self):
        # A question matching the user's reference Q&A is answered locally, $0.
        svc, fake = make_services({"age": "40"})
        svc.reference.add_document(
            "Q: What is your favorite browser? A: Google Chrome\n"
            "Q: What is your occupation? A: Software Engineer")
        r = svc.engine.answer("What is your favorite browser?")
        self.assertEqual(r.answer, "Google Chrome")
        self.assertTrue(r.source.is_free)
        self.assertEqual(r.reasoning_code, "REFERENCE_QA_MATCH")
        self.assertEqual(fake.calls, 0)

    def test_reference_paraphrase_semantic_match(self):
        # Differently-worded question still matches the reference Q&A for FREE
        # via semantic search (requires the embedding model).
        from app.retrieval.embedding_manager import EmbeddingManager
        if not EmbeddingManager.instance().available():
            self.skipTest("embedding model unavailable")
        svc, fake = make_services({"age": "40"})
        svc.reference.add_document(
            "Q: What is your favorite browser? A: Google Chrome")
        r = svc.engine.answer("Which web browser do you use?", allow_api=False)
        self.assertEqual(r.answer, "Google Chrome")
        self.assertEqual(fake.calls, 0)


class TestPersistence(unittest.TestCase):
    def test_survives_reopen(self):
        import tempfile
        from tests.conftest_helpers import _TMP
        from app.services import Services
        path = tempfile.mktemp(suffix=".sqlite3", dir=_TMP)

        svc = Services(db_path=path)
        svc.profile.upsert("age", "39")
        svc.close()

        svc2 = Services(db_path=path)
        self.assertEqual(svc2.profile.as_dict().get("age"), "39")
        svc2.close()


if __name__ == "__main__":
    unittest.main()
