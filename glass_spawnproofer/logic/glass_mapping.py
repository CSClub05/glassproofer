from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

DEFAULT_GLASS = "minecraft:white_stained_glass"

def _package_root() -> Path:
    """Return the package root in source or in a PyInstaller bundle."""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "glass_spawnproofer"
    return Path(__file__).resolve().parents[1]


def _config_path() -> Path:
    return _package_root() / "config" / "default_glass_mappings.json"

# Minecraft dye colors. The order matters: multi-word colors must be checked
# before their single-word suffixes, e.g. light_blue before blue.
DYE_COLORS = [
    "light_blue",
    "light_gray",
    "white",
    "orange",
    "magenta",
    "yellow",
    "lime",
    "pink",
    "gray",
    "cyan",
    "purple",
    "blue",
    "brown",
    "green",
    "red",
    "black",
]

VALID_STAINED_GLASS = {f"minecraft:{color}_stained_glass" for color in DYE_COLORS}


class MappingValidationError(ValueError):
    """Raised when a user-provided glass mapping is malformed."""


def _normalize_block_id(block_id: str) -> str:
    """Return a clean namespace:id without block-state properties.

    This accepts values such as:
    - minecraft:red_concrete
    - red_concrete
    - minecraft:red_concrete[waterlogged=false]
    """
    clean = str(block_id).strip().lower()
    if "[" in clean:
        clean = clean.split("[", 1)[0]
    if not clean:
        raise MappingValidationError("Block IDs cannot be empty.")
    if ":" not in clean:
        clean = f"minecraft:{clean}"
    return clean


def _normalize_glass_id(glass_id: str) -> str:
    """Normalize a stained-glass value.

    Accepts either a full ID such as minecraft:red_stained_glass or a shorthand
    color such as red.
    """
    clean = str(glass_id).strip().lower()
    if not clean:
        raise MappingValidationError("Glass colors cannot be empty.")
    if clean in DYE_COLORS:
        clean = f"minecraft:{clean}_stained_glass"
    elif ":" not in clean:
        clean = f"minecraft:{clean}"

    if clean not in VALID_STAINED_GLASS:
        allowed = ", ".join(DYE_COLORS)
        raise MappingValidationError(
            f"Unsupported glass value '{glass_id}'. Use one of these colors: {allowed}."
        )
    return clean


@lru_cache(maxsize=1)
def _load_default_config() -> dict[str, Any]:
    config_path = _config_path()
    if not config_path.exists():
        return {"default_glass": DEFAULT_GLASS, "exact": {}, "category": []}
    with config_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    exact: dict[str, str] = {}
    for block, glass in data.get("exact", {}).items():
        exact[_normalize_block_id(block)] = _normalize_glass_id(glass)

    category: list[tuple[str, str]] = []
    for item in data.get("category", []):
        contains = str(item.get("contains", "")).strip().lower()
        if not contains:
            continue
        category.append((contains, _normalize_glass_id(item.get("glass", DEFAULT_GLASS))))

    return {
        "default_glass": _normalize_glass_id(data.get("default_glass", DEFAULT_GLASS)),
        "exact": exact,
        "category": category,
    }


def available_glass_colors() -> list[dict[str, str]]:
    """Return color options for the frontend."""
    return [
        {
            "color": color,
            "label": color.replace("_", " ").title(),
            "block_id": f"minecraft:{color}_stained_glass",
        }
        for color in DYE_COLORS
    ]


def default_mapping_payload() -> dict[str, Any]:
    """Return the server-side defaults in a frontend-friendly format."""
    config = _load_default_config()
    return {
        "default_glass": config["default_glass"],
        "exact": dict(sorted(config["exact"].items())),
        "category": [
            {"contains": contains, "glass": glass}
            for contains, glass in config["category"]
        ],
        "colors": available_glass_colors(),
    }


def parse_user_mappings(raw_json: str | None) -> dict[str, str]:
    """Parse user-supplied exact block-to-glass overrides.

    Expected JSON shape from the frontend:
        {"minecraft:gold_block": "minecraft:yellow_stained_glass"}

    Shorthands are also accepted:
        {"gold_block": "yellow"}
    """
    if raw_json is None or not raw_json.strip():
        return {}

    try:
        raw = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise MappingValidationError(f"Custom mapping JSON is invalid: {exc.msg}.") from exc

    if not isinstance(raw, dict):
        raise MappingValidationError("Custom mappings must be a JSON object of block IDs to glass colors.")

    mappings: dict[str, str] = {}
    for block, glass in raw.items():
        mappings[_normalize_block_id(str(block))] = _normalize_glass_id(str(glass))
    return mappings


def _color_from_block_name(block_id: str) -> str | None:
    """Infer a stained-glass color from blocks like red_concrete.

    This handles the common colored block families: concrete, wool,
    terracotta, glazed terracotta, stained glass, stained glass panes,
    carpets, beds, banners, candles, shulker boxes, etc.
    """
    name = block_id.split(":", 1)[1]
    for color in DYE_COLORS:
        if name == color or name.startswith(f"{color}_"):
            return f"minecraft:{color}_stained_glass"
    return None


def glass_for_floor(block_id: str, user_mappings: Mapping[str, str] | None = None) -> str:
    """Return the marker-glass block ID for a spawnable floor block.

    Priority order:
    1. User overrides from the web UI.
    2. Developer defaults from backend/app/config/default_glass_mappings.json.
    3. Automatic dye-prefix detection, such as blue_wool -> blue glass.
    4. Developer category rules from the JSON config.
    5. White stained glass fallback.
    """
    normalized = _normalize_block_id(block_id)
    user_mappings = user_mappings or {}

    if normalized in user_mappings:
        return user_mappings[normalized]

    config = _load_default_config()
    exact = config["exact"]
    if normalized in exact:
        return exact[normalized]

    color_match = _color_from_block_name(normalized)
    if color_match is not None:
        return color_match

    name = normalized.split(":", 1)[1]
    for needle, glass in config["category"]:
        if needle in name:
            return glass

    return config["default_glass"]
