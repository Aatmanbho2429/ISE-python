import webview
import os
import platform                              # ← NEW
import threading
from app.api import Api

api      = Api()
SYSTEM   = platform.system()                # ← NEW  "Windows" or "Darwin"

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))

# ── CHANGED — .icns for macOS, .ico for Windows ───────────────────────
ICON_PATH = os.path.join(BASE_DIR, "visara-logo.icns") if SYSTEM == "Darwin" \
       else os.path.join(BASE_DIR, "visara-logo.ico")

# print(f"[icon] path  : {ICON_PATH}")
# print(f"[icon] exists: {os.path.exists(ICON_PATH)}")


def set_window_icon(window):
    # ── CHANGED — Windows only, skip entirely on macOS ────────────────
    if SYSTEM != "Windows":
        return
    try:
        import ctypes                        # ← moved inside — not needed on macOS
        WM_SETICON      = 0x0080
        ICON_SMALL      = 0
        ICON_BIG        = 1
        LR_LOADFROMFILE = 0x0010

        user32 = ctypes.windll.user32

        hicon_small = user32.LoadImageW(None, ICON_PATH, 1, 16, 16, LR_LOADFROMFILE)
        hicon_big   = user32.LoadImageW(None, ICON_PATH, 1, 48, 48, LR_LOADFROMFILE)

        if hicon_small == 0 or hicon_big == 0:
            return

        hwnd = user32.FindWindowW(None, "Visara")
        if hwnd == 0:
            hwnd = user32.GetForegroundWindow()
        if hwnd == 0:
            return

        user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_small)
        user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG,   hicon_big)
        user32.SetClassLongPtrW(hwnd, -14, hicon_big)

    except Exception as e:
        print(f"[icon] Exception: {e}")


def on_loaded():
    threading.Timer(1.5, lambda: set_window_icon(window)).start()


window = webview.create_window(
    "Visara",
    "http://localhost:4200/",
    js_api=api
)

window.events.loaded += on_loaded

# ── CHANGED — edgechromium + args for Windows, native WebKit for macOS
if SYSTEM == "Windows":
    webview.start(
        gui="edgechromium",
        debug=True,
        http_server=True,
        private_mode=False,
        args=["--allow-file-access-from-files", "--disable-web-security"]
    )
else:
    # macOS — native WebKit, no gui= param needed
    webview.start(
        debug=True,
        http_server=True,
        private_mode=False
    )