"""Builds the *minimal* relevant context for an API request.

Cost control (spec §17, §24): never send the whole profile, reference corpus or
memory. We send only the profile fields most relevant to the question and, if
embeddings are available, the top few reference chunks.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .models import ParsedQuestion
from .profile_resolver import ProfileResolver
from ..retrieval import fuzzy_matcher as F
from ..retrieval.semantic_matcher import SemanticMatcher
from ..utils.config import CONFIG


@dataclass
class BuiltContext:
    profile_context: str
    reference_context: str
    relevant_fields: Dict[str, str]


class ContextBuilder:
    def __init__(self, profile: Dict[str, str], semantic: SemanticMatcher):
        self.profile = profile
        self.resolver = ProfileResolver(profile)
        self.semantic = semantic

    def build(self, q: ParsedQuestion) -> BuiltContext:
        opt_norms = [o.normalized for o in q.options]
        top = self.resolver.top_fields(
            q.normalized, opt_norms, CONFIG.retrieval.max_profile_fields_to_send)
        fields = {m.key: self.profile[m.key] for m in top
                  if m.key in self.profile}
        profile_ctx = "\n".join(f"- {k}: {v}" for k, v in fields.items())

        # Reference retrieval: semantic when available (best), otherwise a fast
        # keyword/fuzzy match so the user's reference data is ALWAYS sent to the
        # AI — this is what makes answers match the user's stated preferences.
        if self.semantic.available:
            ref_chunks = self.semantic.search_reference(q.normalized)
        else:
            ref_chunks = self._keyword_reference(
                q.normalized, CONFIG.retrieval.top_k_reference)
        reference_ctx = "\n---\n".join(ref_chunks)
        # Hard cap the reference tokens sent to the AI (cost control).
        cap = CONFIG.retrieval.max_reference_context_chars
        if len(reference_ctx) > cap:
            reference_ctx = reference_ctx[:cap]

        return BuiltContext(profile_ctx, reference_ctx, fields)

    def _keyword_reference(self, q_norm: str, k: int) -> List[str]:
        """Fast reference retrieval without embeddings (token overlap + fuzzy)."""
        q_tokens = set(q_norm.split())
        if not q_tokens:
            return []
        scored = []
        for ch in self.semantic.reference_repo.all_chunks():
            c_tokens = set(ch.normalized.split())
            overlap = len(q_tokens & c_tokens) / max(1, len(q_tokens))
            score = max(overlap, F.token_set_ratio(q_norm, ch.normalized))
            if score > 0.12:
                scored.append((score, ch.text))
        scored.sort(key=lambda t: t[0], reverse=True)
        return [text for _, text in scored[:k]]
