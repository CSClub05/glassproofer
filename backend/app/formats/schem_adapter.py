from __future__ import annotations

# Stub for the next milestone. Modern .schem files are Sponge NBT schematics.
# The recommended path is: parse Sponge palette/block data with nbtlib, convert it
# into the same internal grid used by the litematic adapter, then write a new
# litematic using litemapy.Region(...).as_schematic(...).


def mark_schem_bytes(file_bytes: bytes, filename: str = "upload.schem"):
    raise NotImplementedError(
        ".schem import is scaffolded but not implemented yet. "
        "This first milestone supports .litematic upload and .litematic download."
    )
