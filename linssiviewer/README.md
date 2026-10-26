# Linssi Viewer

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Read-only photo browser for [Linssi](https://codeberg.org/hiltsu/linssi) SQLite databases.
Browse, search and inspect image metadata without any ML dependencies.

## Features

- Thumbnail grid with async loading
- Full-text search across descriptions, camera names, detected objects and persons
- Filter by date range, camera, YOLO object class, or person name
- EXIF metadata display (camera, lens, GPS, focal length, aperture, ISO, exposure)
- LLM description and detected objects/faces shown in detail panel
- GPS coordinates link directly to OpenStreetMap
- Dark theme (Catppuccin Mocha)

## Requirements

- Python 3.12+
- PySide6, Pillow, PyYAML (no torch, no CUDA, no ML dependencies)

## Installation

```bash
git clone <repo>
cd linssiviewer
bash install.sh
```

Or manually:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
# Open a specific database
python -m src.main --db /path/to/image_analyzer.db

# Open file dialog to choose database
python -m src.main
```

## Database

Linssi Viewer reads the SQLite database produced by the Linssi indexing pipeline.
The database is always opened read-only — no data is ever written or modified.

Expected tables: `images`, `exif_data`, `yolo_detections`, `face_detections`,
`llm_descriptions`, `secondary_dirs`.

## Project structure

```
src/
├── main.py               # Entry point
├── config.py             # AppConfig dataclass
├── database.py           # Read-only SQLite access
└── gui/
    ├── main_window.py    # Three-panel main window
    ├── filter_panel.py   # Search & filter controls
    ├── thumbnail_grid.py # Async thumbnail grid
    ├── detail_panel.py   # Image preview + metadata
    ├── settings_dialog.py# Database info & stats
    └── style.py          # Dark stylesheet
```
