# Copyright 2026 Zsolt Kulcsar and Contributors. Licensed under the EUPL-1.2 or later
"""Persistence contracts."""

import logging

from dataclasses import dataclass
from typing import Literal, Protocol

from cds.model import Record

logger = logging.getLogger(__name__)

RunStatus = Literal["completed", "completed_with_errors", "failed"]


class PersistenceError(RuntimeError):
    """Represent a fatal persistence operation failure."""


@dataclass(frozen=True)
class PersistRunInput:
    """Describe all values needed to persist one pipeline run.

    Attributes:
        root_path: Source root path analyzed in this run.
        provider_url: LLM provider endpoint URL.
        model: LLM model identifier.
        scope: Comma-separated scope argument used for enrichment.
        progress_batch_size: Progress emission batch size used by enrichment.
        analyzer_error_count: Number of recoverable analyzer errors.
        records: Final records to persist.
    """

    root_path: str
    provider_url: str
    model: str
    scope: str
    progress_batch_size: int
    analyzer_error_count: int
    records: list[Record]


@dataclass(frozen=True)
class PersistRunResult:
    """Represent the persisted run summary."""

    run_id: int
    record_count: int
    intent_failed_count: int
    analyzer_error_count: int
    status: RunStatus


class Persistence(Protocol):
    """Define the contract for persisting one run snapshot."""

    def persist_run(self, payload: PersistRunInput) -> PersistRunResult:
        """Persist one complete run snapshot."""
