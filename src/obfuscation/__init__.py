# Copyright 2026 Zsolt Kulcsar and Contributors. Licensed under the EUPL-1.2 or later
"""Public import surface for obfuscation components."""

from obfuscation.analyzer import ProjectIndex, analyze_project
from obfuscation.mapper import RenameMap, build_rename_map
from obfuscation.rewriter import RewriteError, RewriteResult, rewrite_source

__all__ = [
    "ProjectIndex",
    "RenameMap",
    "RewriteError",
    "RewriteResult",
    "analyze_project",
    "build_rename_map",
    "rewrite_source",
]
