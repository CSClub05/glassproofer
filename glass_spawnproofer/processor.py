from __future__ import annotations

from pathlib import Path
from typing import Mapping

from glass_spawnproofer.formats.litematic_adapter import MarkResult, mark_litematic_bytes
from glass_spawnproofer.formats.schem_adapter import mark_schem_bytes


def process_schematic_file(
    input_path: str | Path,
    output_path: str | Path,
    glass_mappings: Mapping[str, str] | None = None,
) -> MarkResult:
    """Process a schematic file locally and write the marked .litematic output."""
    input_path = Path(input_path)
    output_path = Path(output_path)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file does not exist: {input_path}")

    lower = input_path.name.lower()
    data = input_path.read_bytes()

    if lower.endswith(".litematic"):
        result = mark_litematic_bytes(
            data,
            filename=input_path.name,
            glass_mappings=dict(glass_mappings or {}),
        )
    elif lower.endswith(".schem"):
        result = mark_schem_bytes(data, filename=input_path.name)
    else:
        raise ValueError("Choose a .litematic or .schem file.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(result.data)
    return result
