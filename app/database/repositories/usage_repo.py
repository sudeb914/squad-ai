"""API usage / cost logging and aggregation."""
from __future__ import annotations

from typing import Optional

from ..db import Database
from ...core.models import ApiUsage


class UsageRepo:
    def __init__(self, db: Database):
        self.db = db

    def log(self, usage: ApiUsage) -> int:
        cur = self.db.execute(
            """INSERT INTO api_usage(
                provider, model, input_tokens, output_tokens, cached_tokens,
                estimated_cost_usd, latency_ms, success, error)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (usage.provider, usage.model, usage.input_tokens,
             usage.output_tokens, usage.cached_tokens, usage.estimated_cost_usd,
             usage.latency_ms, 1 if usage.success else 0, usage.error),
        )
        return int(cur.lastrowid)

    def summary(self, since_days: Optional[int] = None,
                provider: Optional[str] = None) -> dict:
        clauses = []
        params: list = []
        if since_days is not None:
            clauses.append("timestamp >= datetime('now', ?)")
            params.append(f"-{since_days} days")
        if provider is not None:
            clauses.append("provider = ?")
            params.append(provider)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        row = self.db.query_one(
            f"""SELECT COUNT(*) calls,
                   COALESCE(SUM(input_tokens),0)  input_tokens,
                   COALESCE(SUM(output_tokens),0) output_tokens,
                   COALESCE(SUM(cached_tokens),0) cached_tokens,
                   COALESCE(SUM(estimated_cost_usd),0) cost,
                   COALESCE(SUM(CASE WHEN success=0 THEN 1 ELSE 0 END),0) failures
               FROM api_usage {where}""",
            tuple(params),
        )
        return {
            "calls": row["calls"], "input_tokens": row["input_tokens"],
            "output_tokens": row["output_tokens"],
            "cached_tokens": row["cached_tokens"],
            "cost": round(row["cost"], 6), "failures": row["failures"],
        }

    def dashboard(self, provider: Optional[str] = None) -> dict:
        """Today / 7-day / all-time totals, optionally scoped to one provider."""
        return {
            "today": self.summary(since_days=1, provider=provider),
            "last_7_days": self.summary(since_days=7, provider=provider),
            "total": self.summary(since_days=None, provider=provider),
        }

    def providers(self) -> list:
        """Distinct provider names that have recorded usage (most-used first)."""
        rows = self.db.query(
            "SELECT provider, COUNT(*) n FROM api_usage "
            "GROUP BY provider ORDER BY n DESC")
        return [r["provider"] for r in rows if r["provider"]]
