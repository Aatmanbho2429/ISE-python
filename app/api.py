import json
from tkinter import filedialog
import os
import platform
import subprocess
from app.config import IMAGE_EXTENSIONS_FOR_FILE
from app.core.progress import get_progress
from app.services import search_service, license_service,sync_service
from app.services import folder_status_service

class Api:
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
    def get_folder_statuses(self):
        return json.dumps(folder_status_service.get_folder_statuses())
    def sync_folder(self, folder_path: str):
        """Index all unindexed images in folder without running a search."""
        import json
        from app.services.sync_service import sync_folder
        from app.core import indexer
        from app.services.search_service import BaseResponse

        response = BaseResponse()
        index    = indexer.load_index()

        sync_folder(index, folder_path, response)
        indexer.save_index(index)

        response.message = (
            "Sync completed with errors" if response.data["errors"]
            else "Sync completed successfully"
        )
        response.code = 207 if response.data["errors"] else 200
        return json.dumps(response.__dict__, indent=2)