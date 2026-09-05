from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5


class BacklogRecordNotFoundError(FileNotFoundError):
    pass


class BacklogStore:
    def __init__(
        self,
        directory: str | Path = "data/pim/backlog",
    ) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(
            parents=True,
            exist_ok=True,
        )

    def create_record(
        self,
        *,
        run_id: str,
        document_id: str,
        chunk_ids: list[str],
        source_text: str,
        ppv_results: list[dict[str, Any]],
        rejection_reasons: list[str],
    ) -> dict[str, Any]:
        backlog_id = str(
            uuid5(
                NAMESPACE_URL,
                f"{run_id}:{document_id}:ppv",
            )
        )

        timestamp = datetime.now(
            timezone.utc
        ).isoformat()

        record = {
            "backlog_id": backlog_id,
            "run_id": run_id,
            "document_id": document_id,
            "workflow_type": "ppv_reprocessing",
            "chunk_ids": chunk_ids,
            "source_text": source_text,
            "ppv_results": ppv_results,
            "rejection_reasons": rejection_reasons,
            "status": "rejected",
            "created_at": timestamp,
            "updated_at": timestamp,
        }

        destination = (
            self.directory
            / f"{backlog_id}.json"
        )

        temporary = destination.with_suffix(
            ".json.tmp"
        )

        temporary.write_text(
            json.dumps(
                record,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        temporary.replace(destination)

        return record

    def load_record(
        self,
        backlog_id: str,
    ) -> dict[str, Any]:
        path = (
            self.directory
            / f"{backlog_id}.json"
        )

        if not path.exists():
            raise BacklogRecordNotFoundError(
                f"Backlog record not found: {backlog_id}"
            )

        return json.loads(
            path.read_text(encoding="utf-8")
        )