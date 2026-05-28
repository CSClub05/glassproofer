# Glass Spawnproofer

A starter FastAPI + vanilla frontend web app for Glass Spawnproofer that uploads a Minecraft schematic, detects potential spawning spaces, places stained-glass markers above them, and downloads a new `.litematic`.

## Current support

- `.litematic` input: implemented
- `.litematic` output: implemented
- `.schem` input: scaffolded for the next milestone, not implemented yet

The detection is conservative and identifies **potential** hostile-mob spawn spaces. A schematic does not include all live-world context that Minecraft uses for actual spawning, such as light updates, biome, dimension, mob type, nearby players, or server settings.

## Project structure

```text
backend/
  app/
    main.py
    config/
      default_glass_mappings.json
    formats/
      litematic_adapter.py
      schem_adapter.py
    logic/
      spawn_rules.py
      glass_mapping.py
  requirements.txt
frontend/
  index.html
  how-it-works.html
  faq.html
  gallery.html
  limitations.html
  privacy.html
  terms.html
  styles.css
  main.js
```

## Run the backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The backend runs at:

```text
http://localhost:8000
```

## Run the frontend

From another terminal:

```bash
cd frontend
python -m http.server 5173
```

Open:

```text
http://localhost:5173
```

## Hidden support pages

For the initial launch, the support/content pages are kept in the project but hidden from the visible site navigation and footer:

- `how-it-works.html`
- `faq.html`
- `gallery.html`
- `limitations.html`
- `privacy.html`
- `terms.html`

They also include `noindex, nofollow` metadata so they are not intended for search indexing while hidden. Re-add them to the navigation/footer when you are ready to launch the full content site. Before publishing those pages, update placeholder contact details in `privacy.html` and `terms.html`, replace the gallery placeholder panels with your own screenshots, and review the legal pages for your jurisdiction.

## Custom glass mappings

Users can add exact block-to-glass overrides in the frontend under **Custom block → glass colors**. These are saved in the browser with `localStorage` and sent with each upload.

Example user override:

```text
minecraft:gold_block -> minecraft:yellow_stained_glass
```

Developers can add app-wide defaults without changing Python code by editing:

```text
backend/app/config/default_glass_mappings.json
```

Use `exact` for block-specific mappings:

```json
{
  "exact": {
    "minecraft:gold_block": "minecraft:yellow_stained_glass"
  }
}
```

Use `category` for broad fallback rules. These are checked in order:

```json
{
  "category": [
    {"contains": "nether_brick", "glass": "minecraft:red_stained_glass"}
  ]
}
```

Restart FastAPI after changing the default JSON file.

## API

```text
GET /api/glass-mappings
```

Returns the server-side default mappings and valid stained-glass colors.

```text
POST /api/mark-spawns
multipart/form-data
file: .litematic
glass_mappings_json: optional JSON object of exact block-to-glass overrides
```

Returns a downloadable `.litematic` with these response headers:

```text
X-Spawn-Candidates
X-Glass-Placed
X-Regions
```

## Next milestones

1. Implement Sponge `.schem` import with `nbtlib`.
2. Add UI options for overwrite behavior and stricter/looser spawn rules.
3. Add a marker preview/report before download.
4. Add tests using tiny generated schematics.
5. Expand support for modded block IDs and shareable mapping preset files.

## Patch note: top-layer spawn spaces

This version treats space above the current top of a region as air during spawn-candidate detection. If a marker needs to be placed above the old top boundary, the `.litematic` region is expanded upward before the stained glass is written.


## Nether wood mappings

The default mapping config includes crimson and warped stem/hyphae variants. Crimson blocks map to red stained glass, and warped blocks map to cyan stained glass. You can change these defaults in `backend/app/config/default_glass_mappings.json` or override them in the web UI.


## Disclaimer

Glass Spawnproofer is an independent tool and is not an official Minecraft product. It is not approved by or associated with Mojang or Microsoft.
