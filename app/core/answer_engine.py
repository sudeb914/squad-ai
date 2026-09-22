"""The single central pipeline every question passes through.

LOCAL FIRST → AI LAST. The engine tries, in order:

  1. Deterministic rules (profile facts, numeric ranges, option mapping)
  2. Exact memory
  3. Fuzzy memory
  4. Semantic memory
  5. DeepSeek fallback — at most ONE call, only when local confidence is
     insufficient, and only through this method.

This is the ONLY place that invokes the AI provider, and every AI call is logged
to ``api_usage``. There is no automatic retry / verification loop.
"""
from __future__ import annotations

import re
import time
from typing import Callable, Dict, List, Optional

from . import confidence as C
from . import normalization as N
from . import question_parser
from .context_builder import ContextBuilder
from .models import AnswerResult, AnswerSource, ParsedQuestion, QuestionType
from .profile_resolver import ProfileResolver
from .reference_answerer import ReferenceAnswerer
from .rule_engine import RuleEngine
from ..database.repositories.memory_repo import MemoryRepo
from ..database.repositories.usage_repo import UsageRepo
from ..memory.answer_memory import AnswerMemory
from ..providers.base_provider import AIRequest, BaseAIProvider
from ..providers.deepseek_provider import SYSTEM_RULES
from ..retrieval import fuzzy_matcher as F
from ..retrieval.exact_matcher import ExactMatcher
from ..retrieval.semantic_matcher import SemanticMatcher
from ..core.models import ApiUsage
from ..utils.config import CONFIG
from ..utils.logging import get_logger

log = get_logger("engine")

# Identity facts DeepSeek cannot know if they aren't in the profile.
_IDENTITY_RE = re.compile(
    r"\b(name|email|e-mail|phone|mobile|address|birth|birthday|dob|zip|"
    r"postal|ssn|username|nickname|surname)\b")

# Short questions that only make sense given the prior turn ("which one?",
# "which model?", "what about it?"). These must not be answered from standalone
# memory, and need the conversation context sent to the AI.
_FOLLOWUP_RE = re.compile(
    r"\b(one|it|that|this|them|those|these|which|model|kind|type|version|"
    r"about|instead|else|then|too|also)\b")


# Explicit references to earlier content (a passage/page shown before). These
# need the conversation history even when the question itself is long.
_CONTEXT_REF_RE = re.compile(
    r"\b(this|the|that|above|previous|preceding) (page|text|passage|paragraph|"
    r"article|document|section|statement|content)\b|\bbased on\b|\bfrom (the|this)\b|"
    r"\bwhat did you\b|\bearlier\b")


def _is_followup(q_norm: str) -> bool:
    words = q_norm.split()
    if not words:
        return False
    # Short AND pronoun/determiner-driven, or explicitly starts with a bare
    # "which/what ...one/model" reference.
    if len(words) <= 5 and _FOLLOWUP_RE.search(q_norm):
        return True
    return False


def _needs_history(q_norm: str) -> bool:
    """Decide (cheaply) whether this question actually needs prior context.

    Send history only when it's a short follow-up OR the question refers to
    earlier content ("based on the page above…"). A self-contained question
    sends none — saving tokens/cost."""
    return _is_followup(q_norm) or bool(_CONTEXT_REF_RE.search(q_norm))

# Provider factory: () -> BaseAIProvider (built fresh so a rotated key is used).
ProviderFactory = Callable[[], Optional[BaseAIProvider]]


class AnswerEngine:
    def __init__(self, *, profile_provider: Callable[[], Dict[str, str]],
                 memory_repo: MemoryRepo, usage_repo: UsageRepo,
                 semantic: SemanticMatcher, answer_memory: AnswerMemory,
                 provider_factory: ProviderFactory,
                 instruction_provider: Optional[Callable[[], str]] = None,
                 profile_info_provider: Optional[Callable[[], str]] = None):
        self._get_profile = profile_provider
        self._get_instructions = instruction_provider or (lambda: "")
        self._get_profile_info = profile_info_provider or (lambda: "")
        self.memory_repo = memory_repo
        self.usage_repo = usage_repo
        self.semantic = semantic
        self.answer_memory = answer_memory
        self.provider_factory = provider_factory
        self.exact = ExactMatcher(memory_repo)
        self.reference_answerer = ReferenceAnswerer(semantic.reference_repo)

    # -- public -----------------------------------------------------------
    def answer(self, text: str, explicit_options: Optional[List[str]] = None,
               allow_api: bool = True, progress: Optional[Callable] = None,
               recent_context: str = "") -> AnswerResult:
        start = time.time()
        q = question_parser.parse(text, explicit_options)
        profile = self._get_profile()

        # A short follow-up in a live chat ("which one?", "which model?") depends
        # on the conversation, so standalone memory would FALSE-match an
        # unrelated stored answer. Skip fuzzy/semantic memory for those and let
        # DeepSeek use the recent context instead.
        followup = bool(recent_context) and _is_followup(q.normalized)

        result = self._try_rules(q, profile, progress)
        if result is None and CONFIG.enable_memory:
            result = self._try_exact_memory(q, progress)
        if result is None and not followup:
            # Reference (the user's curated Q&A) is checked BEFORE the fuzzy
            # memory cache, so trusted answers win over any stale cached ones.
            result = self._try_reference(q, progress)
            if result is None and CONFIG.enable_memory:
                result = (self._try_fuzzy_memory(q, progress)
                          or self._try_semantic_memory(q, progress))

        if result and C.is_locally_resolved(result.confidence):
            return self._finish(q, result, start)

        # Local resolution insufficient -> AI fallback (single call).
        if allow_api:
            api_result = self._try_api(q, profile, progress, recent_context)
            if api_result is not None:
                return self._finish(q, api_result, start)

        if result is not None:  # weak local result, no/failed API
            return self._finish(q, result, start)

        return self._finish(q, AnswerResult(
            answer="", source=AnswerSource.UNRESOLVED, confidence=0.0,
            reasoning_code="NO_LOCAL_MATCH_NO_API", qtype=q.qtype,
            error="Could not resolve locally and DeepSeek was not called."),
            start)

    # -- levels -----------------------------------------------------------
    def _try_rules(self, q, profile, progress) -> Optional[AnswerResult]:
        _emit(progress, "Searching locally...")
        return RuleEngine(profile).resolve(q)

    def _try_exact_memory(self, q, progress) -> Optional[AnswerResult]:
        rec = self.exact.find(q.normalized)
        if rec is None:
            return None
        d = C.decide_reuse("exact", 1.0, q.normalized, rec.question_normalized,
                           [o.normalized for o in q.options], rec.options,
                           rec.confidence)
        if not d.reuse:
            return None
        return self._memory_result(rec, AnswerSource.EXACT_MEMORY, d.confidence,
                                   d.reason, 1.0)

    def _try_fuzzy_memory(self, q, progress) -> Optional[AnswerResult]:
        best_rec = None
        best_score = 0.0
        for rec in self.memory_repo.all():
            s = F.token_set_ratio(q.normalized, rec.question_normalized)
            if s > best_score:
                best_score, best_rec = s, rec
        if best_rec is None:
            return None
        d = C.decide_reuse("fuzzy", best_score, q.normalized,
                           best_rec.question_normalized,
                           [o.normalized for o in q.options], best_rec.options,
                           best_rec.confidence)
        if not d.reuse:
            return None
        return self._memory_result(best_rec, AnswerSource.FUZZY_MEMORY,
                                   d.confidence, d.reason, best_score)

    def _try_semantic_memory(self, q, progress) -> Optional[AnswerResult]:
        if not self.semantic.available:
            return None
        hits = self.semantic.search_memory(q.normalized)
        for hit in hits:
            d = C.decide_reuse("semantic", hit.similarity, q.normalized,
                               hit.record.question_normalized,
                               [o.normalized for o in q.options],
                               hit.record.options, hit.record.confidence)
            if d.reuse:
                return self._memory_result(
                    hit.record, AnswerSource.SEMANTIC_MEMORY, d.confidence,
                    d.reason, hit.similarity)
        return None

    def _try_reference(self, q, progress) -> Optional[AnswerResult]:
        """Answer FREE from the user's reference Q&A (no API) when it matches."""
        pair, score, method = self.reference_answerer.best(q.normalized)
        threshold = (CONFIG.confidence.reference_semantic_min
                     if method == "semantic" else CONFIG.confidence.fuzzy_reuse)
        if pair is None or score < threshold:
            return None
        if not C.intent_compatible(q.normalized, pair.q_norm,
                                   [o.normalized for o in q.options], []):
            return None
        # If the question has options, map the reference answer onto one.
        if q.has_options:
            opt, oscore, code = ProfileResolver({}).map_value_to_option(
                pair.answer, q.options, CONFIG.confidence.fuzzy_profile_option)
            if opt is None:
                return None
            return AnswerResult(
                answer=opt.original, selected_option=opt.original,
                selected_option_index=opt.index, source=AnswerSource.LOCAL_FACT,
                confidence=min(0.95, score), reasoning_code="REFERENCE_QA_MATCH",
                similarity=score, qtype=q.qtype)
        return AnswerResult(
            answer=pair.answer, source=AnswerSource.LOCAL_FACT,
            confidence=min(0.95, score), reasoning_code="REFERENCE_QA_MATCH",
            similarity=score, qtype=q.qtype)

    def _try_api(self, q, profile, progress,
                 recent_context: str = "") -> Optional[AnswerResult]:
        provider = self.provider_factory()
        if provider is None:
            return AnswerResult(
                answer="", source=AnswerSource.UNRESOLVED, confidence=0.0,
                reasoning_code="API_KEY_MISSING", qtype=q.qtype,
                error="AI provider API key is not configured.")
        ctx = ContextBuilder(profile, self.semantic).build(q)

        # Send the user's FULL profile text (small, cheap) so DeepSeek can answer
        # anything in it — children, spouse, etc. — not just keyword-matched
        # fields. Falls back to the structured top-fields when no raw text.
        raw_profile = (self._get_profile_info() or "").strip()
        profile_context = raw_profile[:1800] if raw_profile else ctx.profile_context

        # COST GUARD: an *identity fact* about the user ("what is my name/email
        # /phone …") that isn't in the profile cannot be answered by DeepSeek
        # either — it would reply "cannot determine" and waste money + time.
        # Skip only these; subjective questions ("your favorite…") still go
        # through so the survey can be answered.
        if (not profile_context and not ctx.reference_context
                and re.search(r"\b(my|your|mine|yours)\b", q.normalized)
                and _IDENTITY_RE.search(q.normalized)):
            return AnswerResult(
                answer="", source=AnswerSource.UNRESOLVED, confidence=0.0,
                reasoning_code="NO_CONTEXT_SKIP_API", qtype=q.qtype,
                error="I don't have that in your profile yet — add it in "
                      "⚙ Settings → Profile info.")

        _emit(progress, f"Asking AI ({provider.name})...")
        # Output cap follows the ACTIVE provider so AgentRouter uses its own
        # configured limits; for DeepSeek these equal the previous CONFIG values.
        simple_cap = getattr(provider, "max_output_tokens_simple",
                             CONFIG.provider.max_output_tokens_simple)
        full_cap = getattr(provider, "max_output_tokens",
                           CONFIG.provider.max_output_tokens)
        max_tokens = (simple_cap
                      if q.qtype in (QuestionType.BOOLEAN, QuestionType.FACT,
                                     QuestionType.SINGLE_CHOICE,
                                     QuestionType.NUMERIC,
                                     QuestionType.NUMERIC_RANGE)
                      else full_cap)
        # Send history ONLY when the question needs it (follow-up / refers to a
        # page shown earlier) — self-contained questions send none (cheaper).
        recent_to_send = (recent_context
                          if recent_context and _needs_history(q.normalized)
                          else "")
        req = AIRequest(
            system=SYSTEM_RULES, question=q.original,
            options=[o.original for o in q.options],
            profile_context=profile_context,
            reference_context=ctx.reference_context,
            recent_context=recent_to_send,
            instructions=self._get_instructions() or "",
            max_output_tokens=max_tokens)

        resp = provider.answer(req)  # exactly one call; no retry loop

        cost = provider.estimate_cost(resp.input_tokens, resp.output_tokens,
                                      resp.cached_tokens) if resp.success else 0.0
        usage = ApiUsage(
            provider=provider.name, model=provider.model,
            input_tokens=resp.input_tokens, output_tokens=resp.output_tokens,
            cached_tokens=resp.cached_tokens, estimated_cost_usd=cost,
            latency_ms=resp.latency_ms, success=resp.success, error=resp.error)
        self.usage_repo.log(usage)  # every call logged, success or failure

        if not resp.success:
            return AnswerResult(
                answer="", source=AnswerSource.UNRESOLVED, confidence=0.0,
                reasoning_code="API_FAILED", qtype=q.qtype,
                api_usage=usage, error=resp.error)

        idx = resp.selected_option_index
        selected = None
        reason = "API_FALLBACK"
        if q.has_options:
            # NEVER return an answer outside the given options. Use the model's
            # index if valid; otherwise snap its text to the closest real option.
            if idx is not None and 0 <= idx < len(q.options):
                selected = q.options[idx].original
            else:
                best_i, _ = F.best_match(
                    N.normalize(resp.answer), [o.normalized for o in q.options])
                if best_i is not None:
                    idx = best_i
                    selected = q.options[best_i].original
                    reason = "API_SNAPPED_TO_OPTION"
            answer = selected or (q.options[0].original if q.options else "")
        else:
            answer = resp.answer
        result = AnswerResult(
            answer=answer, source=AnswerSource.DEEPSEEK,
            confidence=resp.confidence or 0.85, reasoning_code=reason,
            selected_option=selected, selected_option_index=idx,
            qtype=q.qtype, api_usage=usage)
        result.debug["relevant_fields"] = ctx.relevant_fields
        return result

    # -- helpers ----------------------------------------------------------
    def _memory_result(self, rec, source, conf, reason, sim) -> AnswerResult:
        return AnswerResult(
            answer=rec.answer, source=source, confidence=conf,
            reasoning_code=reason, selected_option=rec.selected_option,
            selected_option_index=rec.selected_option_index,
            matched_memory_id=rec.id, similarity=sim,
            qtype=QuestionType(rec.category) if rec.category in
            QuestionType.__members__ else QuestionType.UNKNOWN)

    def _finish(self, q: ParsedQuestion, result: AnswerResult,
                start: float) -> AnswerResult:
        result.processing_time_ms = int((time.time() - start) * 1000)
        self.answer_memory.maybe_store(q, result)
        log.info("Q=%r -> %s (%s, conf=%.2f, api=%s, %dms)",
                 q.original[:60], result.answer[:40], result.source.value,
                 result.confidence, result.used_api, result.processing_time_ms)
        return result


def _emit(progress, msg: str) -> None:
    if progress:
        try:
            progress(msg)
        except Exception:  # noqa: BLE001
            pass
