from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class BlockAccessor(Protocol):
    def block_id(self, x: int, y: int, z: int) -> str: ...


@dataclass(frozen=True)
class SpawnCandidate:
    x: int
    y: int
    z: int
    floor_block: str


AIRLIKE = {
    "minecraft:air",
    "minecraft:cave_air",
    "minecraft:void_air",
    "minecraft:light",
}

# Full solid blocks that were previously caught by broad exclusion tokens.
# These should be considered valid potential spawn floors when they have
# enough open space above them.
ALWAYS_SPAWNABLE_FLOOR_EXACT = {
    "minecraft:barrel",
    "minecraft:crafting_table",
    "minecraft:redstone_block",
}

# This deliberately favors false negatives over trashing a schematic with markers.
# Keep broad component terms here, but use ALWAYS_SPAWNABLE_FLOOR_EXACT above
# for full-block exceptions such as redstone_block.
NEVER_SPAWN_FLOOR_CONTAINS = (
    "glass", "slab", "stairs", "fence", "wall", "door", "trapdoor", "button",
    "pressure_plate", "carpet", "rail", "torch", "lantern", "sign", "banner",
    "bed", "chest", "barrel", "shulker_box", "leaves", "sapling", "flower",
    "mushroom", "vines", "water", "lava", "ice", "snow", "cactus", "sugar_cane",
    "redstone", "repeater", "comparator", "hopper", "piston", "observer",
    "enchanting_table", "crafting_table", "furnace", "anvil", "grindstone",
)

REPLACEABLE_MARKER_CONTAINS = (
    "air", "grass", "fern", "flower", "mushroom", "vines", "snow", "seagrass", "kelp"
)


def normalize_block_id(block_id: str) -> str:
    clean = str(block_id).strip()
    if "[" in clean:
        clean = clean.split("[", 1)[0]
    if ":" not in clean:
        clean = f"minecraft:{clean}"
    return clean


def is_airlike(block_id: str) -> bool:
    return normalize_block_id(block_id) in AIRLIKE


def is_replaceable_for_marker(block_id: str) -> bool:
    normalized = normalize_block_id(block_id)
    return normalized in AIRLIKE or any(token in normalized for token in REPLACEABLE_MARKER_CONTAINS)


def is_spawnable_floor(block_id: str) -> bool:
    normalized = normalize_block_id(block_id)
    if normalized in AIRLIKE:
        return False
    if normalized in ALWAYS_SPAWNABLE_FLOOR_EXACT:
        return True
    return not any(token in normalized for token in NEVER_SPAWN_FLOOR_CONTAINS)


def find_spawn_candidates(grid: BlockAccessor, x_range: range, y_range: range, z_range: range) -> list[SpawnCandidate]:
    """Find potential spawn floors.

    Blocks above the top of the schematic are treated as air. This lets exposed
    top-layer surfaces be marked; the format adapter is responsible for growing
    the region upward before it places marker glass outside the old bounds.
    """
    candidates: list[SpawnCandidate] = []
    min_y, max_y = min(y_range), max(y_range)

    def block_or_air_above_bounds(x: int, y: int, z: int) -> str:
        if y > max_y:
            return "minecraft:air"
        if y < min_y:
            return "minecraft:air"
        return grid.block_id(x, y, z)

    for x in x_range:
        for y in y_range:
            for z in z_range:
                floor = grid.block_id(x, y, z)
                if not is_spawnable_floor(floor):
                    continue
                above_1 = block_or_air_above_bounds(x, y + 1, z)
                above_2 = block_or_air_above_bounds(x, y + 2, z)
                if is_replaceable_for_marker(above_1) and is_airlike(above_2):
                    candidates.append(SpawnCandidate(x, y, z, floor))
    return candidates
