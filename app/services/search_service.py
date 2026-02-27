import os
import json
import numpy as np

from app.core import database as db
from app.core import indexer
from app.core.embedder import Embedder
from app.core.progress import set_progress
from app.services.sync_service import sync_folder
from app.utils.image_loader import preprocess_batch_parallel


class BaseResponse:
    def __init__(self):
        self.status  = True
        self.message = ""
        self.code    = 200
        self.data    = {"success": [], "errors": [], "results": []}


def _get_query_embedding(query_image: str) -> "np.ndarray":
    embedder = Embedder()
    batch, valid, failed = preprocess_batch_parallel([query_image])
    if not valid:
        raise RuntimeError(failed[0]["reason"])
    return embedder.embed_batch(batch)[0]


def search(query_image: str, folder_path: str, top_k: int) -> str:
    response    = BaseResponse()
    folder_path = os.path.normpath(folder_path)
    index       = indexer.load_index()

    # Sync folder — embed any new/changed images
    sync_folder(index, folder_path, response)
    indexer.save_index(index)

    # Run similarity search
    set_progress(phase="searching", done=0, total=1, current=os.path.basename(query_image))

    con = db.get_connection()
    try:
        id_map         = db.get_folder_id_map(con, folder_path)
        query          = _get_query_embedding(query_image)
        scores, indices = indexer.search_index(index, query, top_k)

        for rank, (idx, score) in enumerate(zip(indices, scores)):
            if idx in id_map:
                response.data["results"].append({
                    "rank":       rank + 1,
                    "path":       id_map[idx],
                    "similarity": float(score)
                })
    except Exception as e:
        response.status = False
        response.data["errors"].append({"file": query_image, "reason": str(e)})
    finally:
        con.close()

    set_progress(phase="idle", done=1, current="")

    response.message = (
        "Search completed with errors" if response.data["errors"]
        else "Search completed successfully"
    )
    response.code = 207 if response.data["errors"] else 200
    return json.dumps(response.__dict__, indent=2)