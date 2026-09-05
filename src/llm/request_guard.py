from __future__ import annotations

import hashlib
import json
import os
from datetime import date
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


class LLMCallsDisabledError(RuntimeError):
    pass


class LLMRequestBudgetExceeded(RuntimeError):
    pass


class LLMRequestGuard:
    def __init__(
        self,
        runtime_directory: str | Path = "data/runtime",
        cache_directory: str | Path = "data/llm_cache",
    ) -> None:
        load_dotenv()

        self.enabled = (
            os.getenv("ENABLE_LLM_CALLS", "false").lower()
            == "true"
        )

        self.daily_limit = int(
            os.getenv("MAX_LLM_REQUESTS_PER_DAY", "20")
        )

        self.run_limit = int(
            os.getenv("MAX_LLM_REQUESTS_PER_RUN", "3")
        )

        self.runtime_directory = Path(runtime_directory)
        self.cache_directory = Path(cache_directory)

        self.runtime_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.cache_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.ledger_path = (
            self.runtime_directory
            / "llm_request_ledger.json"
        )

        self.run_requests = 0

    @staticmethod
    def create_cache_key(
        model: str,
        operation: str,
        prompt: str,
    ) -> str:
        content = json.dumps(
            {
                "model": model,
                "operation": operation,
                "prompt": prompt,
            },
            sort_keys=True,
            ensure_ascii=False,
        )

        return hashlib.sha256(
            content.encode("utf-8")
        ).hexdigest()

    def read_cache(
        self,
        cache_key: str,
    ) -> dict[str, Any] | None:
        cache_path = (
            self.cache_directory
            / f"{cache_key}.json"
        )

        if not cache_path.exists():
            return None

        return json.loads(
            cache_path.read_text(encoding="utf-8")
        )

    def write_cache(
        self,
        cache_key: str,
        result: dict[str, Any],
    ) -> None:
        cache_path = (
            self.cache_directory
            / f"{cache_key}.json"
        )

        cache_path.write_text(
            json.dumps(
                result,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    def _read_daily_count(self) -> int:
        if not self.ledger_path.exists():
            return 0

        ledger = json.loads(
            self.ledger_path.read_text(
                encoding="utf-8"
            )
        )

        if ledger.get("date") != date.today().isoformat():
            return 0

        return int(ledger.get("requests", 0))

    def _write_daily_count(self, count: int) -> None:
        self.ledger_path.write_text(
            json.dumps(
                {
                    "date": date.today().isoformat(),
                    "requests": count,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def reserve_request(self) -> None:
        if not self.enabled:
            raise LLMCallsDisabledError(
                "LLM calls are disabled. Set "
                "ENABLE_LLM_CALLS=true explicitly."
            )

        if self.run_requests >= self.run_limit:
            raise LLMRequestBudgetExceeded(
                f"Per-run request limit of "
                f"{self.run_limit} reached"
            )

        daily_count = self._read_daily_count()

        if daily_count >= self.daily_limit:
            raise LLMRequestBudgetExceeded(
                f"Daily request limit of "
                f"{self.daily_limit} reached"
            )

        # Reserve before invocation so failed requests are counted.
        self.run_requests += 1
        self._write_daily_count(daily_count + 1)