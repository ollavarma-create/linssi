"""Linssi Web — FastAPI backend entry point."""

import argparse
import os
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import Settings
from database import Database
from routers import images, media

app = FastAPI(title="Linssi Web")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(images.router, prefix="/api")
app.include_router(media.router, prefix="/api")


@app.on_event("startup")
def startup():
    parser = argparse.ArgumentParser(description="Linssi Web backend")
    parser.add_argument("--db", default="", help="Path to the Linssi SQLite database")
    # parse_known_args to ignore uvicorn's own arguments
    args, _ = parser.parse_known_args()

    db_path = args.db or os.environ.get("LINSSI_DB", "")

    if not db_path:
        print(
            "ERROR: No database path provided.\n"
            "Set LINSSI_DB environment variable or pass --db /path/to/image_analyzer.db",
            file=sys.stderr,
        )
        sys.exit(1)

    if not Path(db_path).exists():
        print(f"ERROR: Database file not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    app.state.db = Database(db_path)
    print(f"Loaded database: {db_path}")
