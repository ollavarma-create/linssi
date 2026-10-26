"""Async thumbnail grid using QListWidget + QThreadPool."""

from pathlib import Path

from PIL import Image, ImageOps
from PIL.ImageQt import ImageQt
from PySide6.QtCore import QObject, QRunnable, QSize, Qt, Signal, Slot, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (QListWidget, QListWidgetItem, QSizePolicy, QPushButton, QWidget,
                                QHBoxLayout, QAbstractItemView)


class _WorkerSignals(QObject):
    """Qt signals used by ThumbnailWorker to communicate with the main thread."""

    # QImage is thread-safe; QPixmap must only be used on the main thread
    loaded = Signal(int, QImage)


class ThumbnailWorker(QRunnable):
    """Loads a single thumbnail in a thread pool worker."""

    def __init__(self, image_id: int, file_path: str, cancelled: list[bool]):
        super().__init__()
        self.image_id = image_id
        self.file_path = file_path
        self._cancelled = cancelled
        self.signals = _WorkerSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self):
        """Open, resize, and emit the thumbnail image; silently skips on any error."""
        if self._cancelled[0]:
            return
        try:
            img = Image.open(self.file_path)
            img = ImageOps.exif_transpose(img)  # fix rotation
            img.thumbnail((200, 200))
            img = img.convert("RGB")
            qt_img = ImageQt(img).copy()  # copy so PIL image can be GC'd safely
            if not self._cancelled[0]:
                self.signals.loaded.emit(self.image_id, qt_img)
        except Exception:
            pass  # Keep placeholder on error


class ShowMoreItem(QListWidgetItem):
    """Non-selectable list item that hosts a 'Show more' button for pagination."""

    def __init__(self):
        super().__init__()
        self.setFlags(Qt.ItemFlag.NoItemFlags)
        self.setSizeHint(QSize(210, 60))
        self.button = None

    def create_widget(self) -> QWidget:
        """Build and return the container widget holding the 'Show more' button."""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        self.button = QPushButton("+ Show more images")
        self.button.setMinimumHeight(40)
        layout.addWidget(self.button)

        return container


class ThumbnailGrid(QListWidget):
    """Grid of image thumbnails with async loading and 'Show more' button."""

    load_more_requested = Signal()
    image_selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setIconSize(QSize(200, 200))
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setWordWrap(True)
        self.setSpacing(4)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.itemClicked.connect(self._on_item_clicked)

        self._id_to_item: dict[int, QListWidgetItem] = {}
        self._cancelled: list[bool] = [False]
        self._current_page = 0
        self._page_size = 50
        self._all_results = []
        self._is_loading = False
        self._show_more_item = None
        self._total_loaded = 0

    def scroll_to_file_path(self, file_path: str):
        """Scroll to and highlight the item matching the given file path."""
        target_name = Path(file_path).name

        for i in range(self.count()):
            item = self.item(i)
            if item and target_name in item.text():
                self.clearSelection()
                item.setSelected(True)
                self.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtCenter)

                # Brief highlight to draw attention
                item.setBackground(Qt.GlobalColor.yellow)
                QTimer.singleShot(500, lambda: item.setBackground(Qt.GlobalColor.transparent))
                break

    def load_images(self, results: list[dict], page_size: int = 50):
        """Reset the grid and start loading the first page of results.

        Args:
            results: Full list of image dicts from the database query.
            page_size: Number of thumbnails to show per page.
        """
        self._page_size = page_size
        self.cancel_loading()

        self.clear()
        self._id_to_item.clear()
        self._show_more_item = None

        self._all_results = results
        self._current_page = 0
        self._is_loading = False
        self._total_loaded = 0

        self._load_next_page()

    def _load_next_page(self):
        """Append the next page of thumbnails to the grid and update the Show-more button."""
        if self._is_loading:
            return

        start = self._current_page * self._page_size
        if start >= len(self._all_results):
            self._remove_show_more()
            return

        self._is_loading = True

        self._remove_show_more()

        end = min(start + self._page_size, len(self._all_results))
        page_results = self._all_results[start:end]

        from PySide6.QtCore import QThreadPool

        self._cancelled[0] = True
        self._cancelled = [False]

        for r in page_results:
            image_id = r["id"]
            name = Path(r["file_path"]).name
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, image_id)
            item.setIcon(self.style().standardIcon(
                self.style().StandardPixmap.SP_FileIcon
            ))
            item.setSizeHint(QSize(210, 230))

            self.addItem(item)
            self._id_to_item[image_id] = item
            self._total_loaded += 1

            worker = ThumbnailWorker(image_id, r["file_path"], self._cancelled)
            worker.signals.loaded.connect(self._on_thumbnail_loaded)
            QThreadPool.globalInstance().start(worker)

        self._current_page += 1
        self._is_loading = False

        next_start = self._current_page * self._page_size
        if next_start < len(self._all_results):
            self._add_show_more()
        else:
            self._add_summary_item()

    def _add_show_more(self):
        """Append the ShowMoreItem to the list and wire its button to load the next page."""
        self._show_more_item = ShowMoreItem()
        self.addItem(self._show_more_item)

        widget = self._show_more_item.create_widget()
        self.setItemWidget(self._show_more_item, widget)

        if self._show_more_item.button:
            self._show_more_item.button.clicked.connect(self._on_show_more_clicked)

        loaded = self._total_loaded
        total = len(self._all_results)
        remaining = total - loaded
        if self._show_more_item.button:
            self._show_more_item.button.setText(
                f"+ Show {min(remaining, self._page_size)} more images ({loaded}/{total})")

    def _remove_show_more(self):
        """Remove the ShowMoreItem from the list if it is currently present."""
        if self._show_more_item is not None:
            if self._show_more_item.button:
                try:
                    self._show_more_item.button.clicked.disconnect()
                except Exception:
                    pass
            self.removeItemWidget(self._show_more_item)
            self.takeItem(self.row(self._show_more_item))
            self._show_more_item = None

    def _add_summary_item(self):
        """Append a non-interactive summary row when all pages have been loaded."""
        summary_item = QListWidgetItem(f"📸 All {len(self._all_results)} images loaded")
        summary_item.setFlags(Qt.ItemFlag.NoItemFlags)
        summary_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        summary_item.setSizeHint(QSize(210, 40))
        self.addItem(summary_item)

    def _on_show_more_clicked(self):
        """Handle the 'Show more' button click by loading the next page."""
        self._load_next_page()

    @Slot(int, QImage)
    def _on_thumbnail_loaded(self, image_id: int, qt_image: QImage):
        """Replace the placeholder icon of the given item with the loaded thumbnail."""
        from PySide6.QtGui import QIcon

        item = self._id_to_item.get(image_id)
        if item is not None:
            if self.indexFromItem(item).isValid():
                item.setIcon(QIcon(QPixmap.fromImage(qt_image)))

    def cancel_loading(self):
        """Cancel all pending workers (call before app exit or new search)."""
        self._cancelled[0] = True

    def clear(self):
        """Cancel pending workers and clear all items from the grid."""
        self.cancel_loading()
        super().clear()
        self._id_to_item.clear()
        self._show_more_item = None
        self._total_loaded = 0

    def _on_item_clicked(self, item: QListWidgetItem):
        """Emit image_selected with the image_id when a thumbnail item is clicked."""
        if item is self._show_more_item:
            return

        image_id = item.data(Qt.ItemDataRole.UserRole)
        if image_id is not None:
            self.image_selected.emit(image_id)
