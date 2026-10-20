from __future__ import annotations

import threading
import time
from typing import Any


class Metrics:
    """Aggregate, non-identifying AI usage counters for diagnostics.

    Prompts, plan content, event details, and credentials are never recorded.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started_at = time.time()
        self._values: dict[str, Any] = {
            "ai_requests": 0,
            "ai_successes": 0,
            "ai_failures": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "thought_tokens": 0,
            "total_tokens": 0,
            "latency_ms_total": 0,
            "last_latency_ms": None,
            "last_model": None,
            "last_error_category": None,
            "last_call_at": None,
            "transient_retries": 0,
            "schema_validation_failures": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "generations": 0,
            "revisions": 0,
            "quota_events": 0,
        }

    def increment(self, name: str, amount: int = 1) -> None:
        with self._lock:
            self._values[name] = self._values.get(name, 0) + amount

    def record_ai_request(
        self,
        *,
        model: str,
        latency_ms: int,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        thought_tokens: int | None = None,
        total_tokens: int | None = None,
        error_category: str | None = None,
    ) -> None:
        with self._lock:
            self._values["ai_requests"] += 1
            if error_category:
                self._values["ai_failures"] += 1
                self._values["last_error_category"] = error_category
                if error_category == "quota":
                    self._values["quota_events"] += 1
            else:
                self._values["ai_successes"] += 1
            for name, value in (
                ("input_tokens", input_tokens),
                ("output_tokens", output_tokens),
                ("thought_tokens", thought_tokens),
                ("total_tokens", total_tokens),
            ):
                if value:
                    self._values[name] += int(value)
            self._values["latency_ms_total"] += max(0, latency_ms)
            self._values["last_latency_ms"] = max(0, latency_ms)
            self._values["last_model"] = model
            self._values["last_call_at"] = time.time()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            values = dict(self._values)
        requests = values["ai_requests"]
        values["average_latency_ms"] = (
            round(values["latency_ms_total"] / requests, 1) if requests else None
        )
        values["uptime_seconds"] = round(time.time() - self._started_at, 1)
        return values

    def reset(self) -> None:
        with self._lock:
            for key in self._values:
                self._values[key] = 0 if isinstance(self._values[key], int) else None
            self._started_at = time.time()


metrics = Metrics()
