# Copyright 2026 Zsolt Kulcsar and Contributors. Licensed under the EUPL-1.2 or later
"""Database backends for the code duplication scanner."""

from cds.database.sqlite import SQLitePersistence

__all__ = ["SQLitePersistence"]
