#!/usr/bin/env bash
set -euo pipefail
python3 -m pip install -r requirements.txt
python3 -m PyInstaller --onefile --windowed --name "Glass Spawnproofer" --add-data "glass_spawnproofer/config/default_glass_mappings.json:glass_spawnproofer/config" run.py
