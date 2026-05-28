@echo off
python -m pip install -r requirements.txt
python -m PyInstaller --onefile --windowed --name "Glass Spawnproofer" --manifest app.manifest --add-data "glass_spawnproofer\config\default_glass_mappings.json;glass_spawnproofer\config" run.py
pause
