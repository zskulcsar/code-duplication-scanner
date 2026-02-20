# Copyright 2026 Zsolt Kulcsar and Contributors. Licensed under the EUPL-1.2 or later
"""LLM client abstractions."""

import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class IntentGenerationError(RuntimeError):
    """Represent an intent generation failure."""


class LLMClient(Protocol):
    """Define intent generation behavior for a provider client."""

    def generate_intent(self, code: str) -> str:
        """Generate intent text from code.

        Args:
            code: Normalized code snippet.

        Returns:
            Generated intent text.

        Raises:
            IntentGenerationError: If generation fails or response is malformed.
        """
