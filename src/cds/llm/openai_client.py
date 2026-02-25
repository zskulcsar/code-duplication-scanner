# Copyright 2026 Zsolt Kulcsar and Contributors. Licensed under the EUPL-1.2 or later
"""LLM client OpenAI implementation."""

import logging
from urllib.parse import urlparse

from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    NotFoundError,
    OpenAI,
    OpenAIError,
    PermissionDeniedError,
    RateLimitError,
)

from cds.llm_client import IntentGenerationError

logger = logging.getLogger(__name__)

OPENAI_CODEX_MODEL: str = "gpt-5.2-codex"
OPENAI_DEFAULT_BASE_URL: str = "https://api.openai.com/v1"


class OpenAIClient:
    """Generate intent using OpenAI's Responses API."""

    def __init__(
        self,
        provider_url: str,
        model: str = OPENAI_CODEX_MODEL,
    ) -> None:
        """Initialize client configuration.

        Args:
            provider_url: OpenAI-compatible endpoint base URL.
            model: Model identifier used for generation.
        """
        self._provider_url = provider_url
        self._model = model
        self._client: OpenAI | None = None

    def generate_intent(self, code: str) -> str:
        """Generate intent text with OpenAI Responses API.

        Args:
            code: Normalized code snippet.

        Returns:
            Generated intent text.

        Raises:
            IntentGenerationError: If request fails or response has no content.
        """
        client = self._get_client()
        try:
            response = client.responses.create(
                model=self._model,
                instructions=(
                    "Summarize the intent of the provided code snippet "
                    "in one short sentence."
                ),
                input=code,
            )
        except (
            APIConnectionError,
            APIError,
            APITimeoutError,
            AuthenticationError,
            BadRequestError,
            InternalServerError,
            NotFoundError,
            PermissionDeniedError,
            RateLimitError,
            AttributeError,
            OSError,
            ValueError,
        ) as exc:
            logger.warning(
                f"OpenAI request failed (provider_url={self._provider_url} "
                f"model={self._model} error={exc})"
            )
            raise IntentGenerationError(str(exc)) from exc

        content = _extract_response_content(response)
        if not content:
            logger.warning(
                f"OpenAI response did not contain intent content "
                f"(provider_url={self._provider_url} model={self._model} response={response!r})"
            )
            raise IntentGenerationError(
                "OpenAI response does not contain generation content."
            )
        return content

    def _get_client(self) -> OpenAI:
        """Get or initialize OpenAI SDK client.

        Returns:
            Initialized OpenAI SDK client.

        Raises:
            IntentGenerationError: If client initialization fails.
        """
        if self._client is not None:
            return self._client
        try:
            self._client = OpenAI(base_url=_normalize_provider_url(self._provider_url))
        except (OpenAIError, OSError, ValueError) as exc:
            logger.warning(
                f"OpenAI client initialization failed (provider_url={self._provider_url} "
                f"model={self._model} error={exc})"
            )
            raise IntentGenerationError(str(exc)) from exc
        return self._client


def _normalize_provider_url(provider_url: str) -> str:
    """Normalize OpenAI provider URL to a valid base URL.

    Args:
        provider_url: User-provided provider URL or alias.

    Returns:
        Normalized base URL suitable for OpenAI Python client.

    Raises:
        ValueError: If provider URL is invalid.
    """
    normalized_raw = provider_url.strip()
    if not normalized_raw:
        raise ValueError("Invalid OpenAI provider URL: value is empty.")

    lowered_raw = normalized_raw.lower().rstrip("/")
    if lowered_raw in {"openai", "openai.com", "www.openai.com", "api.openai.com"}:
        return OPENAI_DEFAULT_BASE_URL

    candidate = normalized_raw
    if "://" not in candidate:
        candidate = f"https://{candidate}"

    parsed = urlparse(candidate)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(
            f"Invalid OpenAI provider URL: expected host URL, got '{provider_url}'."
        )

    host = parsed.netloc.lower()
    if host in {"openai.com", "www.openai.com", "api.openai.com"}:
        return OPENAI_DEFAULT_BASE_URL

    return candidate.rstrip("/")


def _extract_response_content(response: object) -> str:
    """Extract generation content from OpenAI response object.

    Args:
        response: OpenAI response object.

    Returns:
        Response content string, or empty string if unavailable.
    """
    if isinstance(response, dict):
        content = response.get("output_text")
        if isinstance(content, str):
            return content.strip()
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str):
        return output_text.strip()
    return ""
