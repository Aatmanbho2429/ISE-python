import base64
import os
import sys
import webview
import tkinter as tk
from tkinter import filedialog

class Api:
    def selectFile(self):
        ("Select file called")
        file_path = filedialog.askopenfilename(
        title="Select a file",
        filetypes=(("Image files", "*.jpg *.jpeg *.png *.bmp *.gif *.tiff *.tif *.webp *.psd *.psb"), ("All files", "*.*")) 
        )
        return file_path
    
    def selectFolder(self):
        folder_path = filedialog.askdirectory(
            title="Select a folder"
        )
        
        return folder_path
        

    def get_system_info(self):
        import platform
        return {
            "os": platform.system(),
            "version": platform.version()
        }

def resource_path(path):
    try:
        base = sys._MEIPASS
    except Exception:
        base = os.path.abspath(".")
    return os.path.join(base, path)

api = Api()

webview.create_window(
    "My App",'http://localhost:4200/',js_api=api
)

# def resource_path(path):
#     try:
#         base_path = sys._MEIPASS
#     except Exception:
#         base_path = os.path.abspath(".")

#     return os.path.join(base_path, path)


# html_path = resource_path(
#     "dist/vynce-standalone/browser/index.html"
# )

# webview.create_window(
#     "My App",
#     html_path,
#     js_api=api
# )

webview.start(gui="edgechromium",
    debug=True,
    http_server=True,
    private_mode=False,
    args=[
        "--allow-file-access-from-files",
        "--disable-web-security"
    ])
