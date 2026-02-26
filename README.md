# Meshy Roblox Bridge

A local bridge application that lets users send Meshy-generated 3D models directly to their Roblox inventory with one click.

---

## For Users

### Requirements

- A [Meshy](https://www.meshy.ai) account (Pro or above)
- A Roblox account

### Download

Download the latest release for your platform from the [Releases](../../releases) page:

| Platform | File |
|----------|------|
| Windows  | `MeshyRobloxBridge.exe` |
| macOS    | `MeshyRobloxBridge.app` |

### Usage

1. **Run** `MeshyRobloxBridge.exe` (Windows) or `MeshyRobloxBridge.app` (macOS)
2. The bridge window opens and shows **Server: Running**
3. Go to [meshy.ai](https://www.meshy.ai), find a model, click **DCC Bridge → Send to Roblox**
4. On first use, authorize your Roblox account in the popup — the bridge shows **Roblox Account: Connected**
5. The model uploads automatically and appears in your Roblox inventory

> **Note:** Keep the bridge window open while using Meshy. You can minimize it.

---

## For Developers

### Architecture

```
Meshy Webapp (browser)
    │
    │  HTTP  localhost:5330
    │
Meshy Roblox Bridge (local app)
    │
    │  Roblox OAuth + Open Cloud API
    │
Roblox Cloud → User Inventory
```

The bridge follows the same DCC Bridge pattern as the Unity/Blender plugins. It runs a local FastAPI server on port `5330` that the Meshy webapp communicates with.

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET  | `/status` | Bridge status and Roblox connection state |
| GET  | `/roblox/authorize` | Generate OAuth authorization URL |
| POST | `/connect` | Open Roblox OAuth in browser |
| GET  | `/roblox/callback` | OAuth redirect handler |
| POST | `/import` | Download model from URL and upload to Roblox |
| GET  | `/upload-status/{id}` | Poll upload operation status |
| POST | `/disconnect` | Revoke token and disconnect |

### Configuration

Key constants at the top of `server.py`:

```python
ROBLOX_CLIENT_ID     = "..."   # Roblox OAuth app credentials
ROBLOX_CLIENT_SECRET = "..."
ROBLOX_REDIRECT_URI  = "http://localhost:5330/roblox/callback"
FRONTEND_URL         = "https://www.meshy.ai"   # CORS origin whitelist
PORT                 = 5330
```

To test against a local or staging frontend, change `FRONTEND_URL` to match the origin (e.g. `http://localhost:3700` or a Vercel preview URL).

### Local Development

```bash
# 1. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run
python server.py
```

The bridge window opens. Use the Meshy webapp (or `curl`) to test the endpoints.

### Project Structure

```
meshy-roblox-plugin/
├── server.py                        # Main application
├── requirements.txt                 # Python dependencies (includes pyinstaller & pillow)
├── assets/
│   ├── icon.ico                     # App icon (Windows)
│   └── MeshyLogo.svg
├── spec/
│   └── MeshyRobloxBridge.spec       # PyInstaller build spec (Windows + macOS)
└── .github/workflows/
    └── build.yml                    # CI build for both platforms
```

### Building

The project uses a single PyInstaller spec file for both platforms. Build must be run on the target platform (cross-compilation is not supported).

```bash
# Install all dependencies including pyinstaller and pillow
pip install -r requirements.txt

# Build (run from project root)
pyinstaller spec/MeshyRobloxBridge.spec
```

Output is in `dist/`:
- Windows → `dist/MeshyRobloxBridge.exe`
- macOS → `dist/MeshyRobloxBridge.app`

**macOS only:** generate `assets/icon.icns` before building (the CI does this automatically):

```bash
mkdir icon.iconset
sips -z 16 16   assets/icon.ico --out icon.iconset/icon_16x16.png
# ... (see .github/workflows/build.yml for the full list)
iconutil -c icns icon.iconset -o assets/icon.icns
```

### CI / Automated Builds

GitHub Actions builds both platforms automatically on every push to `main`.
See [`.github/workflows/build.yml`](.github/workflows/build.yml).

Artifacts are available for download from the Actions run summary page.

### Roblox OAuth App Settings

In [Roblox Creator Hub → Credentials](https://create.roblox.com/credentials), the OAuth app must have:

- **Redirect URI:** `http://localhost:5330/roblox/callback`
- **Scopes:** `openid`, `profile`, `asset:read`, `asset:write`

### Notes

- OAuth credentials are hardcoded for the internal app — do not expose the client secret publicly
- Port `5330` is already included in the Meshy Webapp CSP
- The bridge only allows one instance at a time; launching a second instance shows a warning dialog
