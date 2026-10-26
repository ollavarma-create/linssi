import os
from dataclasses import dataclass


@dataclass
class Settings:
    db_path: str = os.environ.get("LINSSI_DB", "")
    thumbnail_size: tuple[int, int] = (200, 200)
    preview_size: tuple[int, int] = (1200, 1200)
    host: str = "0.0.0.0"
    port: int = 8000
