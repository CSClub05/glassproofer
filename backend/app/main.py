from __future__ import annotations

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from app.formats.litematic_adapter import mark_litematic_bytes
from app.formats.schem_adapter import mark_schem_bytes
from app.logic.glass_mapping import (
    MappingValidationError,
    default_mapping_payload,
    parse_user_mappings,
)

app = FastAPI(title="Glass Spawnproofer", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Spawn-Candidates", "X-Glass-Placed", "X-Regions"],
)


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/glass-mappings")
def glass_mappings():
    """Return default mapping data and valid glass colors for the frontend."""
    return default_mapping_payload()


@app.post("/api/mark-spawns")
async def mark_spawns(
    file: UploadFile = File(...),
    glass_mappings_json: str | None = Form(default=None),
):
    filename = file.filename or "upload.litematic"
    lower = filename.lower()
    data = await file.read()

    try:
        custom_glass_mappings = parse_user_mappings(glass_mappings_json)

        if lower.endswith(".litematic"):
            result = mark_litematic_bytes(
                data,
                filename="upload.litematic",
                glass_mappings=custom_glass_mappings,
            )
        elif lower.endswith(".schem"):
            result = mark_schem_bytes(data, filename="upload.schem")
        else:
            raise HTTPException(status_code=400, detail="Upload a .litematic or .schem file.")
    except MappingValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not process schematic: {exc}") from exc

    out_name = filename.rsplit('.', 1)[0] + "_spawn_marked.litematic"
    headers = {
        "Content-Disposition": f'attachment; filename="{out_name}"',
        "X-Spawn-Candidates": str(result.candidates),
        "X-Glass-Placed": str(result.placed),
        "X-Regions": str(result.regions),
    }
    return Response(content=result.data, media_type="application/octet-stream", headers=headers)
