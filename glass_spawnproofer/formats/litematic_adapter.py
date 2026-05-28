from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

import nbtlib
from nbtlib.tag import Compound, Int, List, Long, String
from litemapy import BlockState, Region, Schematic

from glass_spawnproofer.logic.glass_mapping import glass_for_floor
from glass_spawnproofer.logic.spawn_rules import find_spawn_candidates


@dataclass
class MarkResult:
    data: bytes
    input_format: str
    regions: int
    candidates: int
    placed: int


class LitematicRegionAccessor:
    def __init__(self, region):
        self.region = region

    def block_id(self, x: int, y: int, z: int) -> str:
        return self.region.getblock(x, y, z).blockid


def _region_ranges(region):
    return region.xrange(), region.yrange(), region.zrange()


def _load_nbt_lenient(path: Path) -> Compound:
    """Load a litematic NBT file, accepting both gzipped and plain NBT."""
    try:
        return nbtlib.File.load(str(path), gzipped=True)
    except Exception:
        return nbtlib.File.load(str(path), gzipped=False)


def _axis_bounds(position: int, size: int) -> tuple[int, int]:
    """
    Match litemapy's schematic-coordinate bounds for a region axis.

    Litematica region sizes can be negative. For positive sizes, x=0 size=10
    covers 0..9. For negative sizes, x=0 size=-10 covers -9..0.
    """
    if size > 0:
        return position, position + size - 1
    return position + size + 1, position


def _compute_enclosing_size(regions: Compound) -> Compound:
    mins: list[int | None] = [None, None, None]
    maxs: list[int | None] = [None, None, None]

    for region in regions.values():
        pos = region["Position"]
        size = region["Size"]
        for i, axis in enumerate(("x", "y", "z")):
            low, high = _axis_bounds(int(pos[axis]), int(size[axis]))
            mins[i] = low if mins[i] is None else min(mins[i], low)
            maxs[i] = high if maxs[i] is None else max(maxs[i], high)

    if any(v is None for v in mins + maxs):
        return Compound({"x": Int(0), "y": Int(0), "z": Int(0)})

    return Compound(
        {
            "x": Int(maxs[0] - mins[0] + 1),
            "y": Int(maxs[1] - mins[1] + 1),
            "z": Int(maxs[2] - mins[2] + 1),
        }
    )


def _ensure_litematic_defaults(nbt: Compound) -> Compound:
    """
    Some exported .litematic files omit metadata keys that litemapy treats as
    mandatory, especially Metadata.EnclosingSize. Fill safe defaults before
    handing the file to litemapy.
    """
    if "Regions" not in nbt:
        raise ValueError("This file does not look like a Litematica .litematic file: missing Regions tag")

    metadata = nbt.setdefault("Metadata", Compound())
    if "EnclosingSize" not in metadata:
        metadata["EnclosingSize"] = _compute_enclosing_size(nbt["Regions"])

    metadata.setdefault("Author", String(""))
    metadata.setdefault("Description", String(""))
    metadata.setdefault("Name", String("Uploaded schematic"))
    metadata.setdefault("TimeCreated", Long(0))
    metadata.setdefault("TimeModified", Long(0))
    metadata.setdefault("RegionCount", Int(len(nbt["Regions"])))
    metadata.setdefault("TotalBlocks", Int(0))
    metadata.setdefault("TotalVolume", Int(0))

    nbt.setdefault("Version", Int(6))
    nbt.setdefault("SubVersion", Int(1))
    nbt.setdefault("MinecraftDataVersion", Int(3700))

    # Litemapy also expects these region list tags to exist.
    for region in nbt["Regions"].values():
        region.setdefault("Entities", List[Compound]([]))
        region.setdefault("TileEntities", List[Compound]([]))
        region.setdefault("PendingBlockTicks", List[Compound]([]))
        region.setdefault("PendingFluidTicks", List[Compound]([]))

    return nbt


def _load_litematic_schematic(path: Path) -> Schematic:
    raw_nbt = _load_nbt_lenient(path)
    fixed_nbt = _ensure_litematic_defaults(raw_nbt)
    return Schematic.from_nbt(fixed_nbt)


def _copy_region_with_extra_top_space(region, required_marker_y: int):
    """Return a region tall enough to contain required_marker_y.

    Litemapy regions cannot be resized in place. If a marker has to be placed
    above the old top Y, create a larger region, copy the old block data, and
    return the Y-coordinate shift needed for candidate placement.

    Positive-height regions keep the same local Y coordinates. Negative-height
    regions are converted to a positive-height region spanning the same old
    vertical bounds plus the new top space; their old local Y coordinates shift
    upward by -old_min_y.
    """
    old_y_range = region.yrange()
    old_min_y, old_max_y = min(old_y_range), max(old_y_range)
    if required_marker_y <= old_max_y:
        return region, 0

    if region.height > 0:
        new_region_y = region.y
        new_height = required_marker_y + 1
        y_shift = 0
    else:
        new_region_y = region.y + old_min_y
        new_height = required_marker_y - old_min_y + 1
        y_shift = -old_min_y

    expanded = Region(region.x, new_region_y, region.z, region.width, new_height, region.length)

    for x in region.xrange():
        for y in region.yrange():
            for z in region.zrange():
                expanded[x, y + y_shift, z] = region[x, y, z]

    expanded.entities.extend(region.entities)
    expanded.tile_entities.extend(region.tile_entities)
    expanded.block_ticks.extend(region.block_ticks)
    expanded.fluid_ticks.extend(region.fluid_ticks)

    if y_shift:
        for entity in expanded.entities:
            px, py, pz = entity.position
            entity.position = (px, py + y_shift, pz)
        for tile_entity in expanded.tile_entities:
            px, py, pz = tile_entity.position
            tile_entity.position = (px, py + y_shift, pz)

    return expanded, y_shift


def mark_litematic_bytes(
    file_bytes: bytes,
    filename: str = "upload.litematic",
    glass_mappings: dict[str, str] | None = None,
) -> MarkResult:
    with tempfile.TemporaryDirectory() as td:
        in_path = Path(td) / filename
        out_path = Path(td) / "marked.litematic"
        in_path.write_bytes(file_bytes)

        schematic = _load_litematic_schematic(in_path)
        total_candidates = 0
        total_placed = 0

        for region_name, region in list(schematic.regions.items()):
            accessor = LitematicRegionAccessor(region)
            xr, yr, zr = _region_ranges(region)
            candidates = find_spawn_candidates(accessor, xr, yr, zr)
            total_candidates += len(candidates)

            if candidates:
                required_marker_y = max(candidate.y + 1 for candidate in candidates)
                region, y_shift = _copy_region_with_extra_top_space(region, required_marker_y)
                schematic.regions[region_name] = region
            else:
                y_shift = 0

            for candidate in candidates:
                glass_id = glass_for_floor(candidate.floor_block, glass_mappings)
                region.setblock(candidate.x, candidate.y + 1 + y_shift, candidate.z, BlockState(glass_id))
                total_placed += 1

        schematic.save(str(out_path))
        return MarkResult(
            data=out_path.read_bytes(),
            input_format="litematic",
            regions=len(schematic.regions),
            candidates=total_candidates,
            placed=total_placed,
        )
