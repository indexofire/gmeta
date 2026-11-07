"""Priority pathogen annotation against the built-in surveillance list."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from gmeta.report.models import TaxonRow

_DATA = Path(__file__).resolve().parent.parent / "data" / "priority_pathogens.json"


@lru_cache(maxsize=1)
def load_priority_table() -> dict[str, dict[str, str]]:
    """Normalised lookup: every alias / species name (lower) → entry."""
    table: dict[str, dict[str, str]] = {}
    for entry in json.loads(_DATA.read_text()):
        names = [entry["name"], *entry.get("aliases", [])]
        for name in names:
            table[name.lower()] = entry
    return table


def lookup(name: str) -> dict[str, str] | None:
    """Exact (case-insensitive) match on species name or alias."""
    return load_priority_table().get(name.strip().lower())


def annotate(rows: list[TaxonRow]) -> list[TaxonRow]:
    """Set ``priority`` / ``priority_category`` in place; returns the same list."""
    for row in rows:
        entry = lookup(row.name)
        if entry:
            row.priority = True
            row.priority_category = f"{entry['zh_name']}（{entry['category']}）"
    return rows
