import os
from concurrent.futures import ThreadPoolExecutor

from app.config import BATCH_SIZE, NUM_WORKERS
from app.core import database as db
from app.core import indexer
from app.core.progress import set_progress, get_progress
from app.core.embedder import Embedder
from app.utils.file_utils import fast_hash, scan_images
from app.utils.image_loader import preprocess_batch_parallel


def sync_folder(index, folder_path: str, response) -> None:
    folder_path     = os.path.normpath(folder_path)
    current_files   = list(scan_images(folder_path))
    seen_hashes     = set()
    needs_embedding = []

    con = db.get_connection()
    db.cleanup_missing(con)

    # ── Step 1: Hash all files in parallel ──────────────────────────────
    set_progress(done=0, total=len(current_files), current="", phase="hashing", errors=0)
    hashed_done = 0

    def hash_one(path):
        try:
            current_mtime = os.path.getmtime(path)

            # Check if file exists in DB with same mtime — skip disk read if so
            existing = db.find_by_path(con, path)
            if existing and abs(existing[2] - current_mtime) < 0.001:
                # mtime unchanged — reuse stored hash, no disk read needed
                return path, existing[1], None, current_mtime, True  # True = skipped

            # mtime changed or new file — compute hash from disk
            h = fast_hash(path)
            return path, h, None, current_mtime, False  # False = hashed

        except Exception as e:
            return path, None, str(e), 0.0, False

    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as ex:
        for result in ex.map(hash_one, current_files):
            path, h, err, mtime, skipped = result
            hashed_done += 1
            set_progress(done=hashed_done, current=os.path.basename(path))

            if err:
                set_progress(errors=get_progress()["errors"] + 1)
                response.status = False
                response.data["errors"].append({"file": path, "reason": err})
                continue

            seen_hashes.add(h)
            existing_path, existing_faiss_id = db.find_by_hash(con, h)

            if existing_faiss_id is not None:
                # Hash already indexed
                if existing_path != path:
                    # File was renamed/moved — update path only
                    db.move_file(con, existing_path, path)
                    con.commit()
                response.data["success"].append(path)
            else:
                # ── Content-change orphan fix ────────────────────────────
                # Check if this path already exists in DB with a DIFFERENT hash
                # (means file content was edited) — remove old FAISS vector first
                existing_by_path = db.find_by_path(con, path)
                if existing_by_path:
                    old_faiss_id = existing_by_path[0]
                    indexer.remove_embeddings(index, [old_faiss_id])
                    db.delete_file(con, path)
                    con.commit()
                # ────────────────────────────────────────────────────────
                needs_embedding.append((path, h, mtime))

    # ── Step 2: Embed new/changed files in batches ───────────────────────
    total    = len(needs_embedding)
    done     = 0
    embedder = Embedder()

    set_progress(done=0, total=total if total > 0 else 1, phase="embedding")

    for i in range(0, total, BATCH_SIZE):
        chunk       = needs_embedding[i:i + BATCH_SIZE]
        batch_paths = [p for p, _, _ in chunk]
        hash_lookup  = {p: h     for p, h, _ in chunk}
        mtime_lookup = {p: mtime for p, _, mtime in chunk}

        set_progress(current=os.path.basename(batch_paths[0]))

        batch, valid_paths, failed = preprocess_batch_parallel(batch_paths)

        for f in failed:
            set_progress(errors=get_progress()["errors"] + 1)
            response.status = False
            response.data["errors"].append(f)

        if batch is not None:
            embs = embedder.embed_batch(batch)
            for path, emb in zip(valid_paths, embs):
                faiss_id = db.get_next_faiss_id(con)
                indexer.add_embedding(index, emb, faiss_id)
                db.insert_file(con, path, hash_lookup[path], faiss_id, mtime_lookup[path])
                response.data["success"].append(path)
            con.commit()

        done += len(chunk)
        set_progress(done=done)
        print(f"[sync] {done}/{total} embedded", flush=True)

    # ── Step 3: Remove deleted files ────────────────────────────────────
    all_hashes     = db.get_folder_hashes(con, folder_path)
    deleted_hashes = all_hashes - seen_hashes

    if deleted_hashes:
        rows             = db.get_files_by_hashes(con, deleted_hashes)
        faiss_ids_to_del = []
        for path, faiss_id in rows:
            faiss_ids_to_del.append(faiss_id)
            db.delete_file(con, path)
        indexer.remove_embeddings(index, faiss_ids_to_del)
        con.commit()

    con.close()
    set_progress(done=total, current="", phase="idle")