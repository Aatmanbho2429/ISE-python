import webview
import os
import ctypes
import threading
from app.api import Api

api  = Api()

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
ICON_PATH = os.path.join(BASE_DIR, "visara-logo.ico")

# print(f"[icon] path  : {ICON_PATH}")
# print(f"[icon] exists: {os.path.exists(ICON_PATH)}")

def set_window_icon(window):
    try:
        WM_SETICON     = 0x0080
        ICON_SMALL     = 0
        ICON_BIG       = 1
        LR_LOADFROMFILE = 0x0010

        user32 = ctypes.windll.user32

        hicon_small = user32.LoadImageW(None, ICON_PATH, 1, 16, 16, LR_LOADFROMFILE)
        hicon_big   = user32.LoadImageW(None, ICON_PATH, 1, 48, 48, LR_LOADFROMFILE)  # 48x48 for taskbar

        if hicon_small == 0 or hicon_big == 0:
            return

        # Try finding the hwnd — edgechromium may use a different internal title
        hwnd = user32.FindWindowW(None, "Visara")
        if hwnd == 0:
            # fallback: get the foreground window
            hwnd = user32.GetForegroundWindow()
        if hwnd == 0:
            return

        user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_small)
        user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG,   hicon_big)

        # This forces the taskbar to refresh the icon
        user32.SetClassLongPtrW(hwnd, -14, hicon_big)  # GCL_HICON = -14

    except Exception as e:
        print(f"[icon] ❌ Exception: {e}")

# def set_window_icon(window):
#     """
#     pywebview's icon= param doesn't work on edgechromium/Windows.
#     We use the Win32 API directly to set both the title-bar icon
#     and the taskbar icon after the window is ready.
#     """
#     try:
#         # Win32 constants
#         WM_SETICON    = 0x0080
#         ICON_SMALL    = 0        # title-bar icon  (16×16 / 32×32)
#         ICON_BIG      = 1        # taskbar icon    (32×32 / 48×48)
#         LR_LOADFROMFILE = 0x0010

#         user32  = ctypes.windll.user32
#         kernel32 = ctypes.windll.kernel32

#         # Load icon from file (let Windows pick the best size)
#         hicon_small = user32.LoadImageW(
#             None,
#             ICON_PATH,
#             1,           # IMAGE_ICON
#             16, 16,
#             LR_LOADFROMFILE
#         )
#         hicon_big = user32.LoadImageW(
#             None,
#             ICON_PATH,
#             1,           # IMAGE_ICON
#             32, 32,
#             LR_LOADFROMFILE
#         )

#         # Find the window handle by title
#         hwnd = user32.FindWindowW(None, "Visara")

#         if hwnd == 0:
#             # print("[icon] ❌ Could not find window handle")
#             return

#         if hicon_small == 0 or hicon_big == 0:
#             # print(f"[icon] ❌ Could not load icon — small:{hicon_small} big:{hicon_big}")
#             # print(f"[icon]    Check the .ico file is valid and at: {ICON_PATH}")
#             return

#         # Send WM_SETICON to the window
#         user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_small)
#         user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG,   hicon_big)

#         # print("[icon] ✅ Icon set successfully")

#     except Exception as e:
#         print(f"[icon] ❌ Exception: {e}")

def on_loaded():
    threading.Timer(1.5, lambda: set_window_icon(window)).start()

# def on_loaded():
#     """Called by pywebview when the page finishes loading."""
#     # Small delay to ensure the native window is fully initialised
#     threading.Timer(0.5, lambda: set_window_icon(window)).start()


# window = webview.create_window(
#     "Visara",
#     "http://localhost:4200/",
#     js_api=api
# )

window = webview.create_window(
    "Visara",
    os.path.join(BASE_DIR, "UI", "dist", "vynce-standalone", "browser", "index.html"),
    js_api=api
)

# Hook into the page-loaded event so the Win32 handle exists by the time we run
window.events.loaded += on_loaded

# webview.start(
#     gui="edgechromium",
#     debug=True,
#     http_server=True,
#     private_mode=False,
#     args=["--allow-file-access-from-files", "--disable-web-security"]
# )
webview.start(
    gui="edgechromium",
    debug=True,
    private_mode=False,
)