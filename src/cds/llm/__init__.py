# Copyright 2026 Zsolt Kulcsar and Contributors. Licensed under the EUPL-1.2 or later
"""LLM client implementations for the code duplication scanner."""

from cds.llm.openai_client import OPENAI_CODEX_MODEL, OpenAIClient
from cds.llm.ollama import OllamaClient

__all__ = ["OllamaClient", "OpenAIClient", "OPENAI_CODEX_MODEL"]
