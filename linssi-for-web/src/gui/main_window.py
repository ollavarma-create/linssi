"""Main application window."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMainWindow, QSplitter

from src.gui.detail_panel import DetailPanel
from src.gui.filter_panel import FilterPanel
from src.gui.thumbnail_grid import ThumbnailGrid

if TYPE_CHECKING:
    from src.config import AppConfig
    from src.database import Database


class MainWindow(QMainWindow):
    """Three-panel main window: filter | thumbnails | detail."""

    def __init__(self, db: Database, config: AppConfig):
        super().__init__()
        self._db = db
        self.setWindowTitle("Linssi Viewer")

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._filter_panel = FilterPanel(db, config)
        self._thumbnail_grid = ThumbnailGrid()
        self._detail_panel = DetailPanel()

        splitter.addWidget(self._filter_panel)
        splitter.addWidget(self._thumbnail_grid)
        splitter.addWidget(self._detail_panel)
        splitter.setSizes([200, 460, 540])

        self.setCentralWidget(splitter)

        # Connect signals
        self._filter_panel.search_requested.connect(self._on_search)
        self._thumbnail_grid.image_selected.connect(self._on_image_selected)
        self._detail_panel.show_in_grid_requested.connect(self._on_show_in_grid)

        # Load images on startup
        self._on_search({})

    def _on_show_in_grid(self, file_path: str):
        """Scroll the thumbnail grid to the given file path and highlight it."""
        self._thumbnail_grid.scroll_to_file_path(file_path)

    def _on_search(self, filters: dict):
        """Run search and pass all results to the thumbnail grid (grid handles paging)."""
        limit = filters.pop("limit", 50)
        results = self._db.get_images(**filters, limit=0)  # fetch all, grid pages
        self._thumbnail_grid.load_images(results, page_size=limit)

    def _on_image_selected(self, image_id: int):
        """Show full metadata for the selected image in the detail panel."""
        self._detail_panel.show_image(image_id, self._db)

    def closeEvent(self, event):
        """Cancel pending thumbnail workers and wait for the thread pool before closing."""
        from PySide6.QtCore import QThreadPool
        self._thumbnail_grid.cancel_loading()
        QThreadPool.globalInstance().clear()
        QThreadPool.globalInstance().waitForDone()
        super().closeEvent(event)
