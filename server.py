"""
Meshy Roblox Bridge - 本地 Bridge 应用

用于将 Meshy 生成的 3D 模型一键上传到 Roblox 平台。
此应用在本地运行，通过 localhost:5330 与 Meshy Webapp 通信。

启动方式:
  cd scripts/roblox-test-server
  pip install -r requirements.txt
  python server.py

API 端点（兼容 DCC Bridge 模式）:
  GET  /status          - 检查 Bridge 状态和 Roblox 连接状态
  POST /connect         - 触发 Roblox OAuth 授权
  POST /import          - 接收模型 URL 并上传到 Roblox
  GET  /upload-status/  - 轮询上传状态
"""

import base64
import datetime
import hashlib
import html
import io
import json
import os
import platform
import queue
import secrets
import sys
import threading
import time
import tkinter as tk
import webbrowser
import zipfile
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

# ============ Configuration ============

ROBLOX_CLIENT_ID = "5736123519074675650"
ROBLOX_CLIENT_SECRET = "RBX-u7klWvZeE0qQPSgwTqMPihH3ExBCDV0YlQ4gv1WEkWQnlH40U_CjUgRScRl-VbAy"
ROBLOX_REDIRECT_URI = "http://localhost:5330/roblox/callback"

FRONTEND_URL = "https://meshy-webapp-pr-5137-taichi-dev.vercel.app"
PORT = 5330

# Roblox OAuth endpoints
ROBLOX_AUTH_URL = "https://apis.roblox.com/oauth/v1/authorize"
ROBLOX_TOKEN_URL = "https://apis.roblox.com/oauth/v1/token"
ROBLOX_USERINFO_URL = "https://apis.roblox.com/oauth/v1/userinfo"
ROBLOX_REVOKE_URL = "https://apis.roblox.com/oauth/v1/token/revoke"
ROBLOX_ASSETS_URL = "https://apis.roblox.com/assets/v1/assets"

SCOPES = "openid profile asset:read asset:write"
# ============ In-memory storage ============

oauth_states: dict[str, dict] = {}
user_tokens: dict = {}
upload_operations: dict[str, dict] = {}

# ============ App Setup ============

app = FastAPI(title="Meshy Roblox Bridge")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ Helper Functions ============


def generate_pkce() -> tuple[str, str]:
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return code_verifier, code_challenge


def get_auth_header() -> str:
    credentials = f"{ROBLOX_CLIENT_ID}:{ROBLOX_CLIENT_SECRET}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


async def refresh_access_token() -> bool:
    if not user_tokens.get("refresh_token"):
        return False

    async with httpx.AsyncClient() as client:
        response = await client.post(
            ROBLOX_TOKEN_URL,
            headers={
                "Authorization": get_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "refresh_token",
                "refresh_token": user_tokens["refresh_token"],
            },
        )

    if response.status_code == 200:
        data = response.json()
        user_tokens.update({
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token", user_tokens["refresh_token"]),
            "expires_at": time.time() + data.get("expires_in", 900),
        })
        print(f"[Token] Refreshed. Expires in {data.get('expires_in', 900)}s")
        return True
    else:
        print(f"[Token] Refresh failed: {response.status_code} {response.text}")
        return False


async def get_valid_access_token() -> "str | None":
    if not user_tokens.get("access_token"):
        return None

    if user_tokens.get("expires_at", 0) < time.time() + 60:
        success = await refresh_access_token()
        if not success:
            return None

    return user_tokens["access_token"]


# ============ DCC Bridge Compatible Endpoints ============


@app.get("/status")
async def status():
    """
    检查 Bridge 状态（兼容 DCC Bridge /status 接口）
    Webapp 通过此接口判断 Bridge 是否在运行
    """
    return {
        "status": "ok",
        "service": "meshy-roblox-bridge",
        "version": "0.1.0",
        "connected": bool(user_tokens.get("access_token")),
        "user_info": user_tokens.get("user_info"),
    }


@app.get("/roblox/authorize")
async def roblox_authorize():
    """
    返回 Roblox OAuth 授权 URL（供前端弹窗使用）
    前端拿到 auth_url 后会在弹窗中打开
    """
    # Clean up expired states (older than 10 minutes)
    cutoff = time.time() - 600
    expired = [k for k, v in oauth_states.items() if v.get("created_at", 0) < cutoff]
    for k in expired:
        del oauth_states[k]

    state = secrets.token_urlsafe(32)
    code_verifier, code_challenge = generate_pkce()

    oauth_states[state] = {
        "code_verifier": code_verifier,
        "created_at": time.time(),
    }

    params = {
        "client_id": ROBLOX_CLIENT_ID,
        "redirect_uri": ROBLOX_REDIRECT_URI,
        "scope": SCOPES,
        "response_type": "code",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }

    auth_url = f"{ROBLOX_AUTH_URL}?{urlencode(params)}"
    print(f"[OAuth] Generated auth URL for popup")

    return {"auth_url": auth_url}


@app.post("/connect")
async def connect():
    """
    触发 Roblox OAuth 授权（Bridge 自行打开浏览器）
    """
    data = await roblox_authorize()
    auth_url = data["auth_url"]
    print(f"[OAuth] Opening browser for authorization...")
    webbrowser.open(auth_url)

    return {"success": True, "message": "Authorization page opened in browser"}


@app.get("/roblox/callback")
async def oauth_callback(code: str = Query(...), state: str = Query(...)):
    """
    OAuth 回调端点
    Roblox 授权成功后会重定向到这里
    """
    print(f"[OAuth] Callback received. State: {state[:8]}..., Code: {code[:8]}...")

    state_data = oauth_states.pop(state, None)
    if not state_data:
        return HTMLResponse(
            content=_result_page("error", "Invalid state parameter. Please try again.", frontend_url=FRONTEND_URL),
            status_code=400,
        )

    code_verifier = state_data["code_verifier"]

    # Exchange code for token
    async with httpx.AsyncClient() as client:
        response = await client.post(
            ROBLOX_TOKEN_URL,
            headers={
                "Authorization": get_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": ROBLOX_REDIRECT_URI,
                "code_verifier": code_verifier,
            },
        )

    if response.status_code != 200:
        error_msg = f"Token exchange failed: {response.status_code} {response.text}"
        print(f"[OAuth] {error_msg}")
        return HTMLResponse(
            content=_result_page("error", error_msg, frontend_url=FRONTEND_URL),
            status_code=400,
        )

    token_data = response.json()
    print(f"[OAuth] Token received successfully!")

    # Get user info
    async with httpx.AsyncClient() as client:
        user_response = await client.get(
            ROBLOX_USERINFO_URL,
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
        )

    user_info = {}
    if user_response.status_code == 200:
        user_info = user_response.json()
        print(f"[OAuth] User: {user_info.get('preferred_username', 'unknown')}")

    # Store tokens
    user_tokens.update({
        "access_token": token_data["access_token"],
        "refresh_token": token_data.get("refresh_token"),
        "expires_at": time.time() + token_data.get("expires_in", 900),
        "user_info": {
            "userId": user_info.get("sub", ""),
            "username": user_info.get("preferred_username", ""),
            "displayName": user_info.get("name", ""),
        },
        "connected_at": time.time(),
    })

    display_name = user_info.get("name", user_info.get("preferred_username", "User"))
    return HTMLResponse(content=_result_page(
        "success",
        display_name,
        frontend_url=FRONTEND_URL,
    ))


class ImportRequest(BaseModel):
    modelUrl: str
    format: str = "glb"
    displayName: str = "Meshy Model"
    description: str = "Created with Meshy AI"


@app.post("/import")
async def import_model(request: ImportRequest):
    """
    接收模型 URL 并上传到 Roblox（兼容 DCC Bridge /import 接口）
    """
    access_token = await get_valid_access_token()
    if not access_token:
        raise HTTPException(status_code=401, detail="Not connected to Roblox. Please run /connect first.")

    user_id = user_tokens.get("user_info", {}).get("userId")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")

    print(f"[Upload] Starting: {request.displayName}")

    # Step 1: Download model file
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
            model_response = await client.get(request.modelUrl)
            if model_response.status_code != 200:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to download model: {model_response.status_code}",
                )
            raw_data = model_response.content
            print(f"[Upload] Model downloaded ({len(raw_data) // 1024} KB)")
    except httpx.TimeoutException:
        raise HTTPException(status_code=408, detail="Model download timed out")

    # Step 1.5: Extract model from ZIP if needed
    # Meshy may return ZIP (e.g. one .glb with embedded textures) or a single file (.glb)
    file_format = request.format
    model_data = raw_data
    if zipfile.is_zipfile(io.BytesIO(raw_data)):
        target_extensions = {
            "fbx": [".fbx"],
            "glb": [".glb"],
            "gltf": [".gltf", ".glb"],
            "obj": [".obj"],
        }
        extensions = target_extensions.get(file_format, [".glb", ".fbx"])
        print(f"[Upload] Extracting {file_format.upper()} from ZIP...")
        with zipfile.ZipFile(io.BytesIO(raw_data)) as zf:
            model_file = None
            for name in zf.namelist():
                if any(name.lower().endswith(ext) for ext in extensions):
                    model_file = name
                    break
            if model_file:
                model_data = zf.read(model_file)
                # Infer format from extension if we were searching multiple
                if model_file.lower().endswith(".glb"):
                    file_format = "glb"
                elif model_file.lower().endswith(".gltf"):
                    file_format = "gltf"
                elif model_file.lower().endswith(".fbx"):
                    file_format = "fbx"
                elif model_file.lower().endswith(".obj"):
                    file_format = "obj"
                print(f"[Upload] Extracted {file_format.upper()} ({len(model_data) // 1024} KB)")
            else:
                all_files = zf.namelist()
                print(f"[Upload] No {file_format} found in ZIP: {all_files}")
                raise HTTPException(
                    status_code=400,
                    detail=f"No {file_format} model file found in ZIP. Contents: {all_files}",
                )
    else:
        print(f"[Upload] {file_format.upper()} file ({len(model_data) // 1024} KB)")

    # Step 2: Upload to Roblox
    request_payload = json.dumps({
        "assetType": "Model",
        "displayName": request.displayName,
        "description": request.description,
        "creationContext": {
            "creator": {
                "userId": user_id,
            },
        },
    })

    format_to_content_type = {
        "fbx": "model/fbx",
        "glb": "model/gltf-binary",
        "gltf": "model/gltf+json",
        "obj": "model/obj",
    }
    content_type = format_to_content_type.get(file_format, "model/gltf-binary")
    file_ext_map = {
        "fbx": "model.fbx",
        "glb": "model.glb",
        "gltf": "model.gltf",
        "obj": "model.obj",
    }
    file_name = file_ext_map.get(file_format, "model.glb")

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            upload_response = await client.post(
                ROBLOX_ASSETS_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                files={
                    "request": (None, request_payload, "application/json"),
                    "fileContent": (file_name, model_data, content_type),
                },
            )
    except httpx.TimeoutException:
        raise HTTPException(status_code=408, detail="Upload to Roblox timed out")

    print(f"[Upload] Uploading to Roblox...")

    if upload_response.status_code not in (200, 201):
        raise HTTPException(
            status_code=upload_response.status_code,
            detail=f"Roblox upload failed: {upload_response.text}",
        )

    result = upload_response.json()
    operation_path = result.get("path", "")
    if not operation_path:
        raise HTTPException(status_code=502, detail="Roblox did not return an operation path")
    operation_id = operation_path.split("/")[-1]

    upload_operations[operation_id] = {
        "status": "processing",
        "created_at": time.time(),
    }

    # Check if already done
    if result.get("done"):
        if result.get("error"):
            error_msg = result["error"].get("message", "Unknown error")
            print(f"[Upload] Immediately failed: {error_msg}")
            upload_operations[operation_id].update({
                "status": "failed",
                "error": error_msg,
            })
            raise HTTPException(status_code=400, detail=error_msg)

        asset_response = result.get("response", {})
        asset_id = str(asset_response.get("assetId", ""))

        if not asset_id:
            print(f"[Upload] Done but no assetId: {result}")
            raise HTTPException(status_code=400, detail="Upload completed but no Asset ID returned")

        print(f"[Upload] Immediately completed: assetId={asset_id}")
        upload_operations[operation_id].update({
            "status": "completed",
            "assetId": asset_id,
            "assetUrl": f"https://create.roblox.com/dashboard/creations/store/{asset_id}/configure",
        })
        return {
            "success": True,
            "result": {
                "operationId": operation_id,
                "status": "completed",
                "assetId": asset_id,
                "assetUrl": f"https://create.roblox.com/dashboard/creations/store/{asset_id}/configure",
            },
        }

    return {
        "success": True,
        "result": {
            "operationId": operation_id,
            "status": "processing",
        },
    }


@app.get("/upload-status/{operation_id}")
async def upload_status(operation_id: str):
    """轮询上传状态"""
    # Clean up expired upload operations (older than 1 hour)
    cutoff = time.time() - 3600
    expired = [k for k, v in upload_operations.items() if v.get("created_at", 0) < cutoff]
    for k in expired:
        del upload_operations[k]

    access_token = await get_valid_access_token()
    if not access_token:
        raise HTTPException(status_code=401, detail="Not connected to Roblox")

    # Return cached completed/failed status
    local_status = upload_operations.get(operation_id)
    if local_status and local_status.get("status") in ("completed", "failed"):
        return {
            "success": local_status.get("status") == "completed",
            "result": {
                "operationId": operation_id,
                "status": local_status["status"],
                "assetId": local_status.get("assetId"),
                "assetUrl": local_status.get("assetUrl"),
                "error": local_status.get("error"),
            },
        }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"https://apis.roblox.com/assets/v1/operations/{operation_id}",
                headers={"Authorization": f"Bearer {access_token}"},
            )
    except httpx.TimeoutException:
        print(f"[Poll] Timeout, retrying...")
        return {"success": True, "result": {"operationId": operation_id, "status": "processing"}}

    print(f"[Poll] Checking upload status...")

    if response.status_code != 200:
        return {"success": True, "result": {"operationId": operation_id, "status": "processing"}}

    data = response.json()

    if data.get("done"):
        # Check if done with error vs done with success
        if data.get("error"):
            error = data["error"]
            error_msg = error.get("message", "Unknown error")
            print(f"[Poll] Upload failed: {error_msg}")
            upload_operations[operation_id].update({
                "status": "failed",
                "error": error_msg,
            })
            return {
                "success": False,
                "result": {
                    "operationId": operation_id,
                    "status": "failed",
                    "error": error_msg,
                },
            }

        asset_response = data.get("response", {})
        asset_id = str(asset_response.get("assetId", ""))

        if not asset_id:
            print(f"[Poll] Upload done but no asset ID returned")
            upload_operations[operation_id].update({
                "status": "failed",
                "error": "Upload completed but no Asset ID returned",
            })
            return {
                "success": False,
                "result": {
                    "operationId": operation_id,
                    "status": "failed",
                    "error": "Upload completed but no Asset ID returned",
                },
            }

        print(f"[Poll] Upload completed!")
        upload_operations[operation_id].update({
            "status": "completed",
            "assetId": asset_id,
            "assetUrl": f"https://create.roblox.com/dashboard/creations/store/{asset_id}/configure",
        })
        return {
            "success": True,
            "result": {
                "operationId": operation_id,
                "status": "completed",
                "assetId": asset_id,
                "assetUrl": f"https://create.roblox.com/dashboard/creations/store/{asset_id}/configure",
            },
        }

    # Not done yet, check for errors in the response
    if data.get("error"):
        error = data["error"]
        error_msg = error.get("message", "Unknown error")
        print(f"[Poll] Upload error: {error_msg[:80]}")
        upload_operations[operation_id].update({
            "status": "failed",
            "error": error_msg,
        })
        return {
            "success": False,
            "result": {
                "operationId": operation_id,
                "status": "failed",
                "error": error_msg,
            },
        }

    return {"success": True, "result": {"operationId": operation_id, "status": "processing"}}


@app.post("/disconnect")
async def disconnect():
    """断开 Roblox 连接"""
    if user_tokens.get("access_token"):
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    ROBLOX_REVOKE_URL,
                    headers={
                        "Authorization": get_auth_header(),
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    data={"token": user_tokens["access_token"]},
                )
        except Exception as e:
            print(f"[OAuth] Token revocation failed: {e}")

    user_tokens.clear()
    print("[OAuth] Disconnected")
    return {"success": True}


# ============ HTML Pages ============


def _result_page(status: str, message: str, frontend_url: str = "http://localhost:3700") -> str:
    if status == "success":
        return f"""
        <!DOCTYPE html>
        <html>
        <head><title>Meshy Roblox Bridge - Connected</title>
        <style>
            body {{ font-family: -apple-system, sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; background: #1a1a2e; color: #fff; }}
            .container {{ text-align: center; padding: 40px; background: #16213e; border-radius: 16px; box-shadow: 0 8px 32px rgba(0,0,0,0.3); }}
            .icon {{ font-size: 64px; margin-bottom: 16px; }}
            h1 {{ margin: 0 0 8px; font-size: 24px; }}
            p {{ color: #a0a0b0; margin: 8px 0; }}
        </style>
        </head>
        <body>
        <div class="container">
            <div class="icon">&#10003;</div>
            <h1>Connected to Roblox!</h1>
            <p>Welcome, {html.escape(message)}</p>
            <p>You can close this window and return to Meshy.</p>
            <p style="color:#666; font-size:12px; margin-top:24px;">This window will close automatically.</p>
        </div>
        <script>
            // Notify the opener (Meshy Webapp popup) that OAuth succeeded
            if (window.opener) {{
                window.opener.postMessage(
                    {{ type: "ROBLOX_OAUTH_SUCCESS" }},
                    {json.dumps(frontend_url)}
                );
            }}
            // Always auto-close -- even if window.opener is lost due to
            // cross-origin navigation (e.g. "Change Account" flow)
            setTimeout(function() {{ window.close(); }}, 2000);
        </script>
        </body>
        </html>
        """
    else:
        return f"""
        <!DOCTYPE html>
        <html>
        <head><title>Meshy Roblox Bridge - Error</title>
        <style>
            body {{ font-family: -apple-system, sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; background: #1a1a2e; color: #fff; }}
            .container {{ text-align: center; padding: 40px; background: #16213e; border-radius: 16px; box-shadow: 0 8px 32px rgba(0,0,0,0.3); max-width: 500px; }}
            .icon {{ font-size: 64px; margin-bottom: 16px; }}
            h1 {{ margin: 0 0 8px; font-size: 24px; color: #ff6b6b; }}
            p {{ color: #a0a0b0; margin: 0; word-break: break-all; }}
        </style>
        </head>
        <body>
        <div class="container">
            <div class="icon">&#10007;</div>
            <h1>Connection Failed</h1>
            <p>{html.escape(message)}</p>
        </div>
        <script>
            if (window.opener) {{
                window.opener.postMessage(
                    {{ type: "ROBLOX_OAUTH_ERROR", error: {json.dumps(message)} }},
                    {json.dumps(frontend_url)}
                );
            }}
        </script>
        </body>
        </html>
        """


# ============ GUI ============


class _StdoutToQueue:
    """Redirect stdout to a queue so the GUI can display it thread-safely."""

    def __init__(self, q: "queue.Queue[str]", original):
        self._q = q
        self._orig = original

    def write(self, text: str):
        stripped = text.rstrip("\n").strip()
        if stripped:
            self._q.put(stripped)
        if self._orig:
            try:
                self._orig.write(text)
            except Exception:
                pass

    def flush(self):
        if self._orig:
            try:
                self._orig.flush()
            except Exception:
                pass


class BridgeGUI:
    # ── Meshy Palette ─────────────────────────────────────────────
    C_BG      = "#181818"   # Meshy black
    C_CARD    = "#1f1f1f"   # card surface
    C_BORDER  = "#2a2a2a"
    C_LIME    = "#C5F955"   # Meshy acid lime  — success / running
    C_PINK    = "#FF3E8F"   # Meshy pink       — error / warning
    C_GRAY    = "#555555"   # idle dot
    C_TEXT    = "#ffffff"
    C_DIM     = "#888888"
    C_LOG_BG  = "#111111"

    # ── Platform-appropriate system fonts (no commercial fonts) ───
    _IS_MAC = platform.system() == "Darwin"
    # Use TkDefaultFont which is guaranteed to exist on all platforms
    FONT_UI   = "TkDefaultFont"
    FONT_MONO = "TkFixedFont"

    def __init__(self, port: int):
        self.port = port
        self._q: "queue.Queue[str]" = queue.Queue()
        self.root = tk.Tk()
        self.root.withdraw()   # hide until fully built to avoid blank flash on macOS
        self._build_window()
        self._build_ui()
        self.root.update_idletasks()
        self.root.deiconify()  # show fully-rendered window

    # ── Window ────────────────────────────────────────────────────

    def _build_window(self):
        # Enable Per-Monitor DPI awareness so the window is crisp on HiDPI screens
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

        self.root.title("Meshy Roblox Bridge")

        # Calculate DPI-aware window size
        # Target: ~15% of screen width, ~20% of screen height
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        # Base size as percentage of screen, with min/max bounds
        win_w = max(300, min(450, int(screen_w * 0.15)))
        win_h = max(350, min(550, int(screen_h * 0.22)))

        self.root.geometry(f"{win_w}x{win_h}+50+50")
        self.root.minsize(280, 320)
        self.root.resizable(True, True)
        self.root.configure(bg=self.C_BG)
        try:
            base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
            self.root.iconbitmap(os.path.join(base, "icon.ico"))
        except Exception:
            pass
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI ────────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_header()
        self._build_status_card()
        self._build_log_area()
        self._build_footer()

    def _build_header(self):
        frm = tk.Frame(self.root, bg=self.C_CARD, pady=12)
        frm.pack(fill=tk.X)
        row = tk.Frame(frm, bg=self.C_CARD)
        row.pack()
        tk.Label(
            row, text="Meshy",
            font=(self.FONT_UI, 14, "bold"),
            fg=self.C_LIME, bg=self.C_CARD,
        ).pack(side=tk.LEFT)
        tk.Label(
            row, text=" Roblox Bridge",
            font=(self.FONT_UI, 14, "bold"),
            fg=self.C_TEXT, bg=self.C_CARD,
        ).pack(side=tk.LEFT)

    def _build_status_card(self):
        outer = tk.Frame(self.root, bg=self.C_BG, padx=12, pady=8)
        outer.pack(fill=tk.X)
        card = tk.Frame(outer, bg=self.C_CARD, padx=12, pady=10)
        card.pack(fill=tk.X)

        self._server_dot, self._server_lbl = self._status_row(card, "Server")
        self._dot_set(self._server_dot, self.C_GRAY)
        self._server_lbl.configure(text="Starting…", fg=self.C_DIM)

        tk.Frame(card, bg=self.C_BORDER, height=1).pack(fill=tk.X, pady=8)

        self._roblox_dot, self._roblox_lbl = self._status_row(card, "Roblox Account")
        self._dot_set(self._roblox_dot, self.C_GRAY)
        self._roblox_lbl.configure(text="Not Connected", fg=self.C_DIM)

    def _status_row(self, parent, label: str):
        row = tk.Frame(parent, bg=self.C_CARD)
        row.pack(fill=tk.X)
        tk.Label(row, text=label, font=(self.FONT_UI, 10),
                 fg=self.C_DIM, bg=self.C_CARD).pack(side=tk.LEFT)
        dot = tk.Canvas(row, width=8, height=8,
                        bg=self.C_CARD, highlightthickness=0)
        dot.pack(side=tk.RIGHT)
        val = tk.Label(row, text="", font=(self.FONT_UI, 10, "bold"),
                       fg=self.C_TEXT, bg=self.C_CARD)
        val.pack(side=tk.RIGHT, padx=(0, 8))
        return dot, val

    def _build_log_area(self):
        outer = tk.Frame(self.root, bg=self.C_BG, padx=12)
        outer.pack(fill=tk.BOTH, expand=True)
        tk.Label(outer, text="Activity Log", font=(self.FONT_UI, 8),
                 fg=self.C_DIM, bg=self.C_BG).pack(anchor=tk.W, pady=(0, 2))
        self._log = tk.Text(
            outer,
            bg=self.C_LOG_BG, fg=self.C_DIM,
            font=(self.FONT_MONO, 8),
            relief=tk.FLAT, padx=8, pady=6,
            wrap=tk.WORD, state=tk.DISABLED,
            height=10,
        )
        self._log.pack(fill=tk.BOTH, expand=True)
        self._log.tag_configure("ts",     foreground="#444444")
        self._log.tag_configure("info",   foreground="#666666")
        self._log.tag_configure("ok",     foreground=self.C_LIME)
        self._log.tag_configure("err",    foreground=self.C_PINK)
        self._log.tag_configure("oauth",  foreground="#aaaaaa")
        self._log.tag_configure("upload", foreground="#cccccc")

    def _build_footer(self):
        frm = tk.Frame(self.root, bg=self.C_CARD, pady=8)
        frm.pack(fill=tk.X, side=tk.BOTTOM)
        tk.Label(
            frm,
            text="Open Meshy Workspace to start",
            font=(self.FONT_UI, 8),
            fg=self.C_DIM, bg=self.C_CARD,
        ).pack()

    # ── Dot helper ────────────────────────────────────────────────

    def _dot_set(self, canvas: tk.Canvas, color: str):
        canvas.delete("all")
        canvas.create_oval(1, 1, 7, 7, fill=color, outline="")

    # ── Logging ───────────────────────────────────────────────────

    def _tag_for(self, msg: str) -> str:
        lo = msg.lower()
        if any(k in lo for k in ("oauth", "token", "auth", "connect", "disconnect")):
            return "oauth"
        if any(k in lo for k in ("upload", "poll", "asset", "download", "zip", "extract")):
            return "upload"
        if any(k in lo for k in ("error", "fail", "exception", "invalid", "denied")):
            return "err"
        if any(k in lo for k in ("success", "completed", "ready", "started", "running")):
            return "ok"
        return "info"

    def _flush_queue(self):
        try:
            while True:
                msg = self._q.get_nowait()
                self._append_log(msg)
        except queue.Empty:
            pass
        self.root.after(80, self._flush_queue)

    def _append_log(self, message: str):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        tag = self._tag_for(message)
        self._log.configure(state=tk.NORMAL)
        self._log.insert(tk.END, f"[{ts}] ", "ts")
        self._log.insert(tk.END, f"{message}\n", tag)
        self._log.see(tk.END)
        total = int(self._log.index("end-1c").split(".")[0])
        if total > 500:
            self._log.delete("1.0", f"{total - 500}.0")
        self._log.configure(state=tk.DISABLED)

    # ── Status setters (thread-safe via root.after) ───────────────

    def _set_server_ok(self):
        self._dot_set(self._server_dot, self.C_LIME)
        self._server_lbl.configure(text="Running", fg=self.C_LIME)

    def _set_server_error(self, text="Error"):
        self._dot_set(self._server_dot, self.C_PINK)
        self._server_lbl.configure(text=text, fg=self.C_PINK)

    def _poll_roblox(self):
        connected = bool(user_tokens.get("access_token"))
        username = (user_tokens.get("user_info") or {}).get("username", "")
        if connected:
            self._dot_set(self._roblox_dot, self.C_LIME)
            self._roblox_lbl.configure(
                text=username or "Connected", fg=self.C_LIME)
        else:
            self._dot_set(self._roblox_dot, self.C_GRAY)
            self._roblox_lbl.configure(text="Not Connected", fg=self.C_DIM)
        self.root.after(2500, self._poll_roblox)

    # ── Server thread ─────────────────────────────────────────────

    def _run_server(self):
        import socket as _sock
        import uvicorn

        # Detect duplicate instance before binding
        probe = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM)
        probe.settimeout(0.5)
        try:
            probe.connect(("127.0.0.1", self.port))
            probe.close()
            self._q.put("Another instance is already running on this port.")
            self.root.after(0, self._on_duplicate)
            return
        except (_sock.timeout, ConnectionRefusedError, OSError):
            probe.close()

        self._q.put(f"Starting server…")
        try:
            import logging
            logging.basicConfig(
                level=logging.WARNING,
                format="%(message)s",
                stream=sys.stdout,
                force=True,
            )
            config = uvicorn.Config(
                app,
                host="127.0.0.1",
                port=self.port,
                log_level="warning",
                access_log=False,
                log_config=None,
            )
            server = uvicorn.Server(config)
            self.root.after(0, self._set_server_ok)
            self._q.put("Server started!")
            self._q.put("Open Meshy Workspace and click Send to Roblox to get started.")
            self._q.put("─" * 25)
            server.run()
        except OSError:
            self._q.put("Port already in use — another instance may be running.")
            self.root.after(0, self._on_duplicate)
        except Exception as exc:
            self._q.put(f"Server error: {exc}")
            self.root.after(0, lambda: self._set_server_error("Error"))

    def _on_duplicate(self):
        import tkinter.messagebox as mb
        self._set_server_error("Already Running")
        mb.showwarning(
            "Already Running",
            f"Meshy Roblox Bridge is already running on port {self.port}.\n\n"
            "Only one instance can run at a time.\n"
            "This window will stay open but the server is inactive.",
        )

    # ── Lifecycle ─────────────────────────────────────────────────

    def _on_close(self):
        self.root.destroy()

    def run(self):
        sys.stdout = _StdoutToQueue(self._q, sys.__stdout__)

        # Enqueue banner before starting the server thread so it always
        # appears first in the log (queue is FIFO, server messages follow).
        for line in [
            "Meshy Roblox Bridge v0.1.0",
            "─" * 25,
        ]:
            self._q.put(line)

        threading.Thread(target=self._run_server, daemon=True).start()
        self.root.after(80, self._flush_queue)
        self.root.after(2500, self._poll_roblox)
        self.root.mainloop()


# ============ Main ============

if __name__ == "__main__":
    BridgeGUI(PORT).run()
