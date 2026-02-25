# Copyright 2026 Zsolt Kulcsar and Contributors. Licensed under the EUPL-1.2 or later
"""Intent enrichment orchestration for analysis records."""

import concurrent.futures
import logging
import time
from dataclasses import replace

from cds.analyzer import SymbolKind
from cds.llm_client import IntentGenerationError, LLMClient
from cds.model import Record

logger = logging.getLogger(__name__)


class IntentEnricher:
    """Enrich records with intent text using an LLM client."""

    def __init__(
        self,
        llm_client: LLMClient,
        progress_batch_size: int = 10,
        max_workers: int = 4,
    ) -> None:
        """Initialize enrichment service.

        Args:
            llm_client: Provider client for intent generation.
            progress_batch_size: Emit progress log line every N completed calls.
            max_workers: Maximum number of worker threads used for enrichment calls.

        Raises:
            ValueError: If ``progress_batch_size`` or ``max_workers`` is not greater
                than zero.
        """
        if progress_batch_size <= 0:
            raise ValueError("progress_batch_size must be > 0")
        if max_workers <= 0:
            raise ValueError("max_workers must be > 0")
        self._llm_client = llm_client
        self._progress_batch_size = progress_batch_size
        self._max_workers = max_workers

    def enrich(self, records: list[Record], scopes: set[SymbolKind]) -> list[Record]:
        """Enrich selected records with intent content.

        Args:
            records: Input records to enrich.
            scopes: Record kinds that should be enriched.

        Returns:
            Enriched records.
        """
        selected_indexes = [
            idx for idx, record in enumerate(records) if record.kind in scopes
        ]
        total = len(selected_indexes)
        if total == 0:
            self._log_progress(completed=0, total=0, failed=0, eta_seconds=0)
            return records

        enriched = list(records)
        completed = 0
        failed = 0
        last_emitted_completed = 0
        cumulative_batch_seconds = 0.0
        cumulative_batch_calls = 0
        batch_started_at = time.monotonic()

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self._max_workers
        ) as executor:
            future_to_index = {
                executor.submit(
                    self._llm_client.generate_intent,
                    enriched[index].normalized_code,
                ): index
                for index in selected_indexes
            }
            for future in concurrent.futures.as_completed(future_to_index):
                index = future_to_index[future]
                record = enriched[index]
                try:
                    intent = future.result()
                    enriched[index] = replace(
                        record,
                        intent=intent,
                        intent_status="success",
                        intent_error=None,
                    )
                except IntentGenerationError as exc:
                    failed += 1
                    logger.warning(
                        f"Intent generation failed for record (file_path={record.file_path} "
                        f"kind={record.kind} error={exc})"
                    )
                    enriched[index] = replace(
                        record,
                        intent=None,
                        intent_status="failed",
                        intent_error=str(exc),
                    )

                completed += 1
                should_emit = (
                    completed % self._progress_batch_size == 0 or completed == total
                )
                if should_emit:
                    now = time.monotonic()
                    elapsed_batch = now - batch_started_at
                    batch_calls = completed - last_emitted_completed
                    if batch_calls > 0:
                        cumulative_batch_seconds += elapsed_batch
                        cumulative_batch_calls += batch_calls
                    avg_seconds_per_call = (
                        cumulative_batch_seconds / cumulative_batch_calls
                        if cumulative_batch_calls > 0
                        else 0.0
                    )
                    remaining = total - completed
                    eta_seconds = int(round(remaining * avg_seconds_per_call))
                    self._log_progress(
                        completed=completed,
                        total=total,
                        failed=failed,
                        eta_seconds=eta_seconds,
                    )
                    last_emitted_completed = completed
                    if completed != total:
                        batch_started_at = time.monotonic()

        return enriched

    def _log_progress(
        self, completed: int, total: int, failed: int, eta_seconds: int
    ) -> None:
        """Emit structured progress log line.

        Args:
            completed: Number of completed enrichment attempts.
            total: Total enrichment attempts for the run.
            failed: Number of failed attempts.
            eta_seconds: Estimated seconds remaining.
        """
        percent = 100.0 if total == 0 else (completed / total) * 100.0
        logger.info(
            "intent_enrichment_progress completed=%s total=%s failed=%s percent=%.2f eta_seconds=%s",
            completed,
            total,
            failed,
            percent,
            eta_seconds,
        )
