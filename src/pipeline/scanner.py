"""Directory scanner and file registration."""
import hashlib
import logging
from pathlib import Path

from tqdm import tqdm

from src.config import AppConfig
from src.database import Database

logger = logging.getLogger("scanner")


def _file_hash(path: Path) -> str:
    """Compute partial MD5 hash of first 64KB for deduplication."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        h.update(f.read(65536))
    return h.hexdigest()


def scan_images(config: AppConfig, db: Database) -> list[tuple[int, str]]:
    """Walk configured image_dirs, register new images in DB, return (image_id, path) list."""
    extensions = {ext.lower() for ext in config.extensions}
    results = []

    for dir_str in config.image_dirs:
        dir_path = Path(dir_str).expanduser().resolve()
        if not dir_path.exists():
            logger.warning(f"Path not found: {dir_path}")
            continue

        excluded = set(config.excluded_dirs)
        files = [
            p for p in dir_path.rglob("*")
            if p.is_file()
            and p.suffix.lower() in extensions
            and not any(part in excluded for part in p.parts)
        ]
        logger.info(f"Found {len(files)} images from path {dir_path}")

        for file_path in tqdm(files, desc=f"Scanning {dir_path.name}", unit="image"):
            try:
                file_hash = _file_hash(file_path)
                file_size = file_path.stat().st_size
                image_id = db.add_image(str(file_path), file_hash, file_size)
                results.append((image_id, str(file_path)))
            except Exception as e:
                logger.warning(f"Error scanning {file_path}: {e}")

    return results
