import json
from tkinter import filedialog
import os
import platform
import subprocess
from app.config import IMAGE_EXTENSIONS_FOR_FILE
from app.core.progress import get_progress
from app.services import search_service, license_service


class Api:
    """Thin pywebview JS bridge — zero business logic."""

    def selectFile(self):
        return filedialog.askopenfilename(
            title="Select an image",
            filetypes=(
                ("Image files", IMAGE_EXTENSIONS_FOR_FILE),
                ("All files", "*.*")
            )
        )

    def selectFolder(self):
        return filedialog.askdirectory(title="Select a folder")

    def validateLicense(self):
        return json.dumps(license_service.validate().__dict__)

    def start_search(self, query_image: str, folder_path: str, top_k):
        return search_service.search(query_image, folder_path, int(top_k))

    def get_progress(self):
        return json.dumps(get_progress())
    def openFilePath(self, path):
        path = os.path.abspath(path)
        folder = os.path.dirname(path)
        system = platform.system()
        try:
            if system == "Darwin":
                subprocess.run(["open", "-R", path])
            elif system == "Windows":
                subprocess.run(["explorer", "/select,", path])
            elif system == "Linux":
                subprocess.run(["xdg-open", folder])
        except Exception:
            pass
        return True