"""Shared JSON envelope for per-method results (aligned with gside)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

METAGENOMIC = "metagenomic_profiling"


@dataclass
class MethodEnvelope:
    """Every profiler returns ``{analysis_type, method, database, result}``."""

    analysis_type: ClassVar[str] = METAGENOMIC
    method: str = ""
    database: dict[str, str] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis_type": self.analysis_type,
            "method": self.method,
            "database": self.database,
            "result": self.result,
        }
