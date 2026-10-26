"""Settings dialog for Linssi Viewer — read-only viewer configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from src.config import AppConfig
    from src.database import Database


class SettingsDialog(QDialog):
    """Simple settings dialog: database info and statistics."""

    def __init__(self, db: "Database", config: "AppConfig", parent=None):
        super().__init__(parent)
        self._db = db
        self._config = config
        self.setWindowTitle("Settings")
        self.setMinimumSize(480, 360)

        layout = QVBoxLayout(self)

        # Database path (read-only display)
        form = QFormLayout()
        self._db_path_edit = QLineEdit(str(db.db_path))
        self._db_path_edit.setReadOnly(True)
        form.addRow("Database:", self._db_path_edit)
        layout.addLayout(form)

        # DB size
        size_mb = db.db_size() / (1024 * 1024)
        self._size_label = QLabel(f"Database size: {size_mb:.1f} MB")
        layout.addWidget(self._size_label)

        # Stats section
        layout.addWidget(QLabel("<b>Statistics</b>"))
        self._stats_label = QLabel()
        self._stats_label.setWordWrap(True)
        layout.addWidget(self._stats_label)
        self._load_stats()

        # Secondary directories (read-only list)
        layout.addWidget(QLabel("<b>Secondary image directories</b>"))
        self._dirs_list = QListWidget()
        self._dirs_list.setMaximumHeight(120)
        layout.addWidget(self._dirs_list)
        self._load_dirs()

        layout.addStretch()

        # OK button
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def _load_stats(self):
        """Load and display database statistics."""
        try:
            s = self._db.stats()
            total = s.get("total_images", 0)
            oldest, newest = self._db.get_date_range()

            def short(d: str) -> str:
                return d[:10] if d else "?"

            date_range = f"{short(oldest)} – {short(newest)}" if (oldest or newest) else "no dates"
            completed = s.get("completed", {})
            exif = completed.get("exif", 0)
            yolo = completed.get("yolo", 0)
            faces = completed.get("faces", 0)
            llm = completed.get("llm", 0)
            self._stats_label.setText(
                f"Images: {total}\n"
                f"Date range: {date_range}\n"
                f"EXIF processed: {exif}  |  Objects: {yolo}  |  Faces: {faces}  |  Descriptions: {llm}"
            )
        except Exception as e:
            self._stats_label.setText(f"Could not load statistics: {e}")

    def _load_dirs(self):
        """Load secondary directories list (read-only)."""
        self._dirs_list.clear()
        try:
            dirs = self._db.get_secondary_dirs()
            for d in dirs:
                self._dirs_list.addItem(d)
            if not dirs:
                self._dirs_list.addItem("(none)")
        except Exception:
            self._dirs_list.addItem("(could not load)")
