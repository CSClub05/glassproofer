# Glass Spawnproofer — Python Desktop App

Glass Spawnproofer is a local desktop application for marking potential spawnable spaces in Minecraft `.litematic` files with stained glass.

This version is a true Python desktop app:

- no website backend
- no GitHub Pages
- no Render
- no Electron
- no HTML/CSS/JavaScript UI

## Run locally

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

macOS/Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

## Build an executable

Windows:

```bat
build_windows.bat
```

macOS/Linux:

```bash
./build_macos_linux.sh
```

The built app will appear in `dist/`.

## High-DPI / blurry text fix

The app enables high-DPI awareness on Windows before Tkinter creates the main window. The Windows build also includes `app.manifest`, which tells Windows not to bitmap-scale the app on high-DPI displays.

If the app still looks blurry on Windows, rebuild it with `build_windows.bat` and make sure the generated executable is the one being opened. If it looks blurry when running from source, use a recent Python installer from python.org, because old Tk builds can render poorly on high-DPI displays.
