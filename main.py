import webview
from app.api import Api

api = Api()

webview.create_window(
    "My App",
    "http://localhost:4200/",
    js_api=api
)

webview.start(
    gui="edgechromium",
    debug=True,
    http_server=True,
    private_mode=False,
    args=["--allow-file-access-from-files", "--disable-web-security"]
)