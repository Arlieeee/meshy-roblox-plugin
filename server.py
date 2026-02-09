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
import hashlib
import io
import json
import os
import secrets
import time
import webbrowser
import zipfile
from urllib.parse import urlencode

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

load_dotenv()

# ============ Configuration ============

ROBLOX_CLIENT_ID = os.getenv("ROBLOX_CLIENT_ID")
ROBLOX_CLIENT_SECRET = os.getenv("ROBLOX_CLIENT_SECRET")
ROBLOX_REDIRECT_URI = os.getenv("ROBLOX_REDIRECT_URI", "http://localhost:5330/roblox/callback")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3700")
PORT = int(os.getenv("PORT", "5330"))

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
    allow_origins=["*"],  # 允许所有来源（本地Bridge不需要限制）
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ Helper Functions ============


def generate_pkce():
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return code_verifier, code_challenge


def get_auth_header():
    credentials = f"{ROBLOX_CLIENT_ID}:{ROBLOX_CLIENT_SECRET}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


async def refresh_access_token():
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


async def get_valid_access_token():
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

    print(f"[Upload] Starting upload...")
    print(f"[Upload] Model URL: {request.modelUrl[:80]}...")
    print(f"[Upload] Display name: {request.displayName}")

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
            print(f"[Upload] Downloaded: {len(raw_data)} bytes")
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
        print(f"[Upload] File is a ZIP archive, looking for {extensions}...")
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
                print(f"[Upload] Extracted '{model_file}': {len(model_data)} bytes (format={file_format})")
            else:
                all_files = zf.namelist()
                print(f"[Upload] ZIP contents: {all_files}")
                raise HTTPException(
                    status_code=400,
                    detail=f"No {file_format} model file found in ZIP. Contents: {all_files}",
                )
    else:
        print(f"[Upload] File is raw {file_format} ({len(model_data)} bytes)")

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

    print(f"[Upload] Roblox response: {upload_response.status_code}")
    print(f"[Upload] Response body: {upload_response.text[:500]}")

    if upload_response.status_code not in (200, 201):
        raise HTTPException(
            status_code=upload_response.status_code,
            detail=f"Roblox upload failed: {upload_response.text}",
        )

    result = upload_response.json()
    operation_path = result.get("path", "")
    operation_id = operation_path.split("/")[-1] if operation_path else "unknown"

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
        print(f"[Poll] Timeout for operation {operation_id}")
        return {"success": True, "result": {"operationId": operation_id, "status": "processing"}}

    print(f"[Poll] Operation {operation_id}: {response.status_code} {response.text[:300]}")

    if response.status_code != 200:
        return {"success": True, "result": {"operationId": operation_id, "status": "processing"}}

    data = response.json()

    if data.get("done"):
        # Check if done with error vs done with success
        if data.get("error"):
            error = data["error"]
            error_msg = error.get("message", "Unknown error")
            print(f"[Poll] Operation {operation_id} FAILED: {error_msg}")
            upload_operations[operation_id] = {
                "status": "failed",
                "error": error_msg,
            }
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
            # done=true but no assetId means something went wrong
            print(f"[Poll] Operation {operation_id} done but no assetId! Response: {data}")
            upload_operations[operation_id] = {
                "status": "failed",
                "error": "Upload completed but no Asset ID returned",
            }
            return {
                "success": False,
                "result": {
                    "operationId": operation_id,
                    "status": "failed",
                    "error": "Upload completed but no Asset ID returned",
                },
            }

        print(f"[Poll] Operation {operation_id} COMPLETED: assetId={asset_id}")
        upload_operations[operation_id] = {
            "status": "completed",
            "assetId": asset_id,
            "assetUrl": f"https://create.roblox.com/dashboard/creations/store/{asset_id}/configure",
        }
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
        print(f"[Poll] Operation {operation_id} error (not done): {error_msg}")
        upload_operations[operation_id] = {
            "status": "failed",
            "error": error_msg,
        }
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
            <p>Welcome, {message}</p>
            <p>You can close this window and return to Meshy.</p>
            <p style="color:#666; font-size:12px; margin-top:24px;">This window will close automatically.</p>
        </div>
        <script>
            // Notify the opener (Meshy Webapp popup) that OAuth succeeded
            if (window.opener) {{
                window.opener.postMessage(
                    {{ type: "ROBLOX_OAUTH_SUCCESS" }},
                    "{frontend_url}"
                );
                // Auto-close after a short delay
                setTimeout(function() {{ window.close(); }}, 2000);
            }}
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
            <p>{message}</p>
        </div>
        <script>
            if (window.opener) {{
                window.opener.postMessage(
                    {{ type: "ROBLOX_OAUTH_ERROR", error: "{message}" }},
                    "{frontend_url}"
                );
            }}
        </script>
        </body>
        </html>
        """


# ============ Main ============

if __name__ == "__main__":
    import uvicorn

    print()
    print("=" * 60)
    print("  Meshy Roblox Bridge v0.1.0")
    print("=" * 60)
    print(f"  Port:         {PORT}")
    print(f"  Roblox App:   {ROBLOX_CLIENT_ID}")
    print(f"  Redirect URI: {ROBLOX_REDIRECT_URI}")
    print("=" * 60)
    print()
    print("  Endpoints:")
    print(f"    GET  http://localhost:{PORT}/status           - Bridge status")
    print(f"    POST http://localhost:{PORT}/connect          - Connect Roblox")
    print(f"    POST http://localhost:{PORT}/import           - Upload model")
    print(f"    GET  http://localhost:{PORT}/upload-status/id - Poll status")
    print()
    print("  Ready! Open Meshy Webapp to start using.")
    print("=" * 60)

    uvicorn.run(app, host="0.0.0.0", port=PORT)
