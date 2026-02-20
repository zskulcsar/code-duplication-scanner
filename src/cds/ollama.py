# Copyright 2026 Zsolt Kulcsar and Contributors. Licensed under the EUPL-1.2 or later
"""LLM client Ollama implementation."""

import logging
import ollama

from cds.llm_client import IntentGenerationError

logger = logging.getLogger(__name__)


class OllamaClient:
    """Generate intent using an Ollama provider endpoint."""

    def __init__(self, provider_url: str, model: str) -> None:
        """Initialize client configuration.

        Args:
            provider_url: Ollama endpoint base URL.
            model: Model identifier passed to Ollama.
        """
        self._provider_url = provider_url
        self._model = model
        self._client = ollama.Client(host=provider_url)

    def generate_intent(self, code: str) -> str:
        """Generate intent text with Ollama generate API.

        Args:
            code: Normalized code snippet.

        Returns:
            Generated intent text.

        Raises:
            IntentGenerationError: If request fails or response has no content.
        """
        try:
            response = self._client.generate(
                model=self._model,
                system=(
                    "Summarize the intent of the provided code snippet "
                    "in one short sentence."
                ),
                prompt=code,
                stream=False,
            )
        except (ollama.RequestError, ollama.ResponseError, OSError, ValueError) as exc:
            logger.warning(
                f"Ollama request failed (provider_url={self._provider_url} "
                f"model={self._model} error={exc})"
            )
            raise IntentGenerationError(str(exc)) from exc

        content = _extract_response_content(response)
        if not content:
            logger.warning(
                f"Ollama response did not contain intent content "
                f"(provider_url={self._provider_url} model={self._model} response={response!r})"
            )
            raise IntentGenerationError(
                "Ollama response does not contain generation content."
            )
        return content


def _extract_response_content(response: object) -> str:
    """Extract generation content from Ollama response object.

    Args:
        response: Ollama response object, typically mapping-like.

    Returns:
        Response content string, or empty string if unavailable.
    """
    if isinstance(response, dict):
        content = response.get("response")
        if isinstance(content, str):
            return content.strip()
    content_obj = getattr(response, "response", None)
    if isinstance(content_obj, str):
        return content_obj.strip()
    return ""
