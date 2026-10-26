"""Detail panel showing large image preview and full metadata."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from pathlib import Path

from PIL import Image, ImageOps
from PIL.ImageQt import ImageQt
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QUrl
from PyQt6.QtGui import QPixmap, QDesktopServices
from PyQt6.QtWidgets import (
    QFormLayout,
    QFrame,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QHBoxLayout,
    QPushButton,
    QApplication,
)

if TYPE_CHECKING:
    from src.database import Database


class DetailPanel(QScrollArea):
    """Right panel displaying full metadata for the selected image."""

    show_in_grid_requested = pyqtSignal(str)
    image_deleted = pyqtSignal(int)   # emits image_id after deletion

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        inner = QWidget()
        self.setWidget(inner)
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Large image preview
        self._preview = QLabel()
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setMinimumHeight(200)
        self._preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self._preview)

        # Button row for image actions
        button_row = QHBoxLayout()
        button_row.setSpacing(4)

        self._copy_path_btn = QPushButton("📋 Copy path")
        self._copy_path_btn.setToolTip("Copy image path to clipboard")
        self._copy_path_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._copy_path_btn.clicked.connect(self._copy_path_to_clipboard)
        button_row.addWidget(self._copy_path_btn)

        self._open_folder_btn = QPushButton("📂 Open folder")
        self._open_folder_btn.setToolTip("Open folder containing this image")
        self._open_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._open_folder_btn.clicked.connect(self._open_file_location)
        button_row.addWidget(self._open_folder_btn)

        self._show_in_grid_btn = QPushButton("🔍 Show in grid")
        self._show_in_grid_btn.setToolTip("Scroll to this image in thumbnail grid")
        self._show_in_grid_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._show_in_grid_btn.clicked.connect(self._show_in_grid)
        button_row.addWidget(self._show_in_grid_btn)

        self._delete_btn = QPushButton("🗑 Delete")
        self._delete_btn.setToolTip("Delete this image from disk and database")
        self._delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._delete_btn.setStyleSheet("color: #f38ba8;")
        self._delete_btn.clicked.connect(self._delete_image)
        button_row.addWidget(self._delete_btn)

        button_row.addStretch()  # Push buttons to the left

        layout.addLayout(button_row)

        # File path
        self._path_label = QLabel()
        self._path_label.setWordWrap(True)
        self._path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._path_label)

        # EXIF form
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self._date = QLabel()
        self._camera = QLabel()
        self._gps = QLabel()
        self._gps.setTextFormat(Qt.TextFormat.RichText)
        self._gps.setOpenExternalLinks(True)
        self._gps.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self._focal = QLabel()
        self._aperture = QLabel()
        self._iso = QLabel()
        self._exposure = QLabel()
        self._dims = QLabel()
        form.addRow("Date:", self._date)
        form.addRow("Camera:", self._camera)
        form.addRow("GPS:", self._gps)
        form.addRow("Focal length:", self._focal)
        form.addRow("Aperture:", self._aperture)
        form.addRow("ISO:", self._iso)
        form.addRow("Exposure:", self._exposure)
        form.addRow("Size:", self._dims)
        layout.addLayout(form)

        # Objects
        self._objects_label = QLabel()
        self._objects_label.setWordWrap(True)
        layout.addWidget(QLabel("<b>Objects:</b>"))
        layout.addWidget(self._objects_label)

        # Persons
        self._persons_label = QLabel()
        self._persons_label.setWordWrap(True)
        layout.addWidget(QLabel("<b>Persons:</b>"))
        layout.addWidget(self._persons_label)

        # LLM description
        layout.addWidget(QLabel("<b>Description:</b>"))
        self._description = QTextEdit()
        self._description.setReadOnly(True)
        self._description.setFrameShape(QFrame.Shape.NoFrame)
        self._description.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self._description)

        self._clear_fields()

    def _clear_fields(self):
        """Reset all display widgets to their empty/placeholder state."""
        self._preview.clear()
        self._preview.setText("Select an image")
        self._path_label.clear()
        for lbl in (self._date, self._camera, self._gps, self._focal,
                    self._aperture, self._iso, self._exposure, self._dims,
                    self._objects_label, self._persons_label):
            lbl.clear()
        self._description.clear()
        self._current_image_id = None

    def _show_in_grid(self):
        """Emit show_in_grid_requested with the current image's file path."""
        if hasattr(self, '_current_file_path'):
            self.show_in_grid_requested.emit(self._current_file_path)

    def _copy_path_to_clipboard(self):
        """Copy the current image path to clipboard."""
        if hasattr(self, '_current_file_path') and self._current_file_path:
            clipboard = QApplication.clipboard()
            clipboard.setText(self._current_file_path)

            self._copy_path_btn.setText("✓ Copied!")
            QTimer.singleShot(2000, lambda: self._copy_path_btn.setText("📋 Copy path"))
        else:
            self._copy_path_btn.setText("❌ No image")
            QTimer.singleShot(2000, lambda: self._copy_path_btn.setText("📋 Copy path"))

    def _open_file_location(self):
        """Open file manager at the location of the current image."""
        if hasattr(self, '_current_file_path') and self._current_file_path:
            path = Path(self._current_file_path)
            if path.exists():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))
            else:
                self._open_folder_btn.setText("❌ Not found")
                QTimer.singleShot(2000, lambda: self._open_folder_btn.setText("📂 Open folder"))

    def _delete_image(self):
        """Confirm with the user, then delete the image from disk and the database."""
        from PyQt6.QtWidgets import QMessageBox
        import os

        if not hasattr(self, '_current_image_id') or self._current_image_id is None:
            return
        if not hasattr(self, '_current_file_path') or not self._current_file_path:
            return

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete this image permanently?\n\n{self._current_file_path}\n\n"
            "This will remove the file from disk AND the database.\nThis cannot be undone.",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Ok:
            return

        file_path = self._db.delete_image_by_id(self._current_image_id)

        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
        except OSError as e:
            QMessageBox.warning(self, "File Error", f"Removed from DB but could not delete file:\n{e}")

        deleted_id = self._current_image_id
        self._current_image_id = None
        self._current_file_path = ""
        self._clear_fields()
        self.image_deleted.emit(deleted_id)

    def show_image(self, image_id: int | None, db: Database):
        """Populate panel from DB. Pass None to clear."""
        self._db = db
        if image_id is None:
            self._clear_fields()
            return

        data = db.get_image_detail(image_id)
        if not data:
            self._clear_fields()
            return

        self._current_image_id = image_id
        self._current_file_path = data.get("file_path", "")

        # Preview — use PIL to apply EXIF orientation before displaying
        file_path = self._current_file_path
        try:
            img = Image.open(file_path)
            img = ImageOps.exif_transpose(img)
            img.thumbnail((400, 400))
            img = img.convert("RGB")
            pixmap = QPixmap.fromImage(ImageQt(img).copy())
            self._preview.setPixmap(pixmap)
        except Exception:
            self._preview.setText("Preview not available")

        self._path_label.setText(file_path)

        # EXIF
        self._date.setText(_format_date(data.get("date_taken")))
        make = data.get("camera_make") or ""
        model = data.get("camera_model") or ""
        self._camera.setText(f"{make} {model}".strip() or "–")
        lat, lon = data.get("gps_lat"), data.get("gps_lon")
        if lat and lon:
            url = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}&zoom=15"
            self._gps.setText(
                f'<a href="{url}" style="color:#89b4fa; text-decoration:none;">'
                f"{lat:.6f}, {lon:.6f}</a>"
            )
        else:
            self._gps.setText("–")
        focal = data.get("focal_length")
        self._focal.setText(f"{focal} mm" if focal else "–")
        aperture = data.get("aperture")
        self._aperture.setText(f"f/{aperture}" if aperture else "–")
        self._iso.setText(str(data.get("iso") or "–"))
        self._exposure.setText(data.get("exposure_time") or "–")
        w, h = data.get("width"), data.get("height")
        self._dims.setText(f"{w}×{h}" if w and h else "–")

        # Objects
        objects = data.get("objects", [])
        self._objects_label.setText(
            ", ".join(o["class_name"] for o in objects) if objects else "–"
        )

        # Persons
        persons = data.get("persons", [])
        self._persons_label.setText(
            ", ".join(p["person_name"] for p in persons if p.get("person_name")) if persons else "–"
        )

        # LLM description
        self._description.setPlainText(data.get("description") or "")


def _format_date(date_str: str | None) -> str:
    """Format a DB date string using the locale's short date + time."""
    if not date_str:
        return "–"
    s = date_str.strip()
    for fmt, display_fmt in (
        ("%Y-%m-%d %H:%M:%S", "%x %H:%M"),
        ("%Y-%m-%d %H:%M", "%x %H:%M"),
        ("%Y-%m-%d", "%x"),
    ):
        try:
            return datetime.strptime(s, fmt).strftime(display_fmt)
        except ValueError:
            continue
    # Last resort: try just the date portion
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").strftime("%x")
    except ValueError:
        return date_str
