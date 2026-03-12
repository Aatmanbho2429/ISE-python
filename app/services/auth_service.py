import os
import requests
from app.config import SUPABASE_EDGE, TOKEN_FILE
from app.services.license_service import get_device_id


class AuthResponse:
    def __init__(self):
        self.success  = False
        self.message  = ""
        self.token    = None
        self.user     = None

    def to_dict(self):
        return {
            "success": self.success,
            "message": self.message,
            "token":   self.token,
            "user":    self.user
        }


def login(email: str, password: str) -> AuthResponse:
    resp = AuthResponse()
    try:
        r = requests.post(
            f"{SUPABASE_EDGE}/login-user",
            json={
                "email":     email,
                "password":  password,
                "device_id": get_device_id()
            },
            timeout=15
        )
        data = r.json()

        if not data.get("success"):
            resp.message = data.get("message", "Login failed")
            return resp

        # Save JWT token to file for next app restart
        with open(TOKEN_FILE, "w") as f:
            f.write(data["token"])

        # Decrypt and load ONNX model in memory
        from app.core.embedder import Embedder
        Embedder().set_key(data["onnx_key"])

        resp.success = True
        resp.message = data["message"]
        resp.token   = data["token"]
        resp.user    = data["user"]
        return resp

    except requests.exceptions.ConnectionError:
        resp.message = "No internet connection. Please connect and try again."
        return resp
    except Exception as e:
        resp.message = f"Login error: {str(e)}"
        return resp


def validate_saved_token() -> AuthResponse:
    resp = AuthResponse()

    # No token file — first time, needs login
    if not os.path.exists(TOKEN_FILE):
        resp.message = "No saved session"
        return resp

    try:
        with open(TOKEN_FILE, "r") as f:
            token = f.read().strip()

        r = requests.get(
            f"{SUPABASE_EDGE}/validate-token",
            headers={
                "Authorization": f"Bearer {token}",
                "x-device-id":   get_device_id()
            },
            timeout=10
        )
        data = r.json()

        if not data.get("valid"):
            # Token expired or invalid — delete it, force re-login
            os.remove(TOKEN_FILE)
            resp.message = data.get("message", "Session expired. Please login again.")
            return resp

        # Load ONNX model with key
        from app.core.embedder import Embedder
        Embedder().set_key(data["onnx_key"])

        resp.success = True
        resp.user    = data["user"]
        return resp

    except requests.exceptions.ConnectionError:
        # No internet — allow app to open but model won't load
        resp.success = False
        resp.message = "No internet connection. Please connect to login."
        return resp
    except Exception as e:
        resp.message = str(e)
        return resp


def request_device_reset(email: str, reason: str) -> dict:
    try:
        r = requests.post(
            f"{SUPABASE_EDGE}/request-device-reset",
            json={"email": email, "reason": reason},
            timeout=10
        )
        return r.json()
    except Exception as e:
        return {"success": False, "message": str(e)}


def logout():
    # Delete saved token
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)

    # Unload model from memory
    from app.core.embedder import Embedder
    Embedder().reset()