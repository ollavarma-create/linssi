"""Search/filter controls panel."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCompleter,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from src.config import AppConfig
    from src.database import Database


def _make_completer(items: list[str], starts_with: bool = False) -> QCompleter:
    """Build a case-insensitive QCompleter with contains or starts-with matching.

    Args:
        items: Completion candidates.
        starts_with: When True use starts-with filtering; otherwise use contains.
    """
    if starts_with:
        from PyQt6.QtCore import QSortFilterProxyModel, QStringListModel
        source = QStringListModel(items)
        proxy = QSortFilterProxyModel()
        proxy.setSourceModel(source)
        proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        proxy.setFilterKeyColumn(0)
        c = QCompleter()
        c.setModel(proxy)
        c.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        c.setFilterMode(Qt.MatchFlag.MatchStartsWith)
        c.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        return c
    c = QCompleter(items)
    c.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    c.setFilterMode(Qt.MatchFlag.MatchContains)
    c.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
    return c


class FilterPanel(QWidget):
    """Left panel with search and filter controls."""

    search_requested = pyqtSignal(dict)

    def __init__(self, db: Database, config: AppConfig, parent=None):
        super().__init__(parent)
        self._db = db
        self._config = config
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        self._query = QLineEdit()
        self._query.setPlaceholderText("file, description, camera, object, person…")
        self._query.setToolTip(
            "Search from all text fields at the same time.\n"
"\n"
"Syntax:\n"
"  Jari & dog   → AND: both must exist in the image\n"
"  Jari, Vesa     → OR: either is enough\n"
"  dog          → one search word\n"
"\n"
"Note: YOLO-objectsearch is partial, example 'dog' finds\n"
"also 'hot dog'. Use Object-filed for exact search."
        )
        form.addRow(QLabel("Search:"), self._query)

        self._date_from = QLineEdit()
        self._date_from.setPlaceholderText("YYYY-MM-DD")
        self._date_from.setToolTip(
            "Limit search to image date.\n"
"Date model: YYYY-MM-DD, example 2023-06-15\n"
"Could be used alone or together with To field."
        )
        form.addRow(QLabel("From:"), self._date_from)

        self._date_to = QLineEdit()
        self._date_to.setPlaceholderText("YYYY-MM-DD")
        self._date_to.setToolTip(
            "Limit search to image date.\n"
"Date model: YYYY-MM-DD, example 2023-12-31\n"
"Could be used alone or together with From field."
        )
        form.addRow(QLabel("To:"), self._date_to)

        self._camera = QLineEdit()
        self._camera.setPlaceholderText("e.g. Canon")
        self._camera.setToolTip(
            "Search by camera manufacturer or model.\n"
"Partial search: 'Canon' finds all Canon cameras.\n"
"Automatic filling is available."
        )
        form.addRow(QLabel("Camera:"), self._camera)

        self._obj = QLineEdit()
        self._obj.setPlaceholderText("e.g. dog")
        self._obj.setToolTip(
            "Search by YOLO-objects.\n"
"Partial search: 'dog' finds also 'hot dog'.\n"
"Automatic filling is available."
        )
        form.addRow(QLabel("Object:"), self._obj)

        self._person = QLineEdit()
        self._person.setPlaceholderText("e.g. Hemmo")
        self._person.setToolTip(
            "Search by identified person name.\n"
"Exact search: 'Esa' does not find 'Vesa'.\n"
"Automatic filling is available."
        )
        form.addRow(QLabel("Person:"), self._person)

        layout.addLayout(form)

        limit_row = QHBoxLayout()
        limit_row.addWidget(QLabel("Limit search:"))
        self._limit = QSpinBox()
        self._limit.setRange(0, 99999)
        self._limit.setValue(50)
        self._limit.setSpecialValueText("All")
        self._limit.setToolTip("Max results to load into thumbnail grid (0 = all)")
        limit_row.addWidget(self._limit)
        layout.addLayout(limit_row)

        btn_search = QPushButton("Search")
        btn_search.clicked.connect(self._emit_search)
        layout.addWidget(btn_search)

        btn_clear = QPushButton("Clear")
        btn_clear.clicked.connect(self._clear)
        layout.addWidget(btn_clear)

        # Stats section
        self._stats_widget = QWidget()
        stats_layout = QVBoxLayout(self._stats_widget)
        stats_layout.setContentsMargins(0, 4, 0, 4)
        stats_layout.setSpacing(6)

        # Basic stats
        self._basic_stats = QLabel()
        self._basic_stats.setStyleSheet("font-size: 11px; font-weight: bold;")
        stats_layout.addWidget(self._basic_stats)

        # Top cameras
        self._top_cameras = QLabel()
        self._top_cameras.setStyleSheet("font-size: 11px;")
        stats_layout.addWidget(self._top_cameras)

        # Top objects
        self._top_objects = QLabel()
        self._top_objects.setStyleSheet("font-size: 11px;")
        stats_layout.addWidget(self._top_objects)

        # Top persons
        self._top_persons = QLabel()
        self._top_persons.setStyleSheet("font-size: 11px;")
        stats_layout.addWidget(self._top_persons)

        # Top locations
        self._top_locations = QLabel()
        self._top_locations.setStyleSheet("font-size: 11px;")
        stats_layout.addWidget(self._top_locations)

        layout.addWidget(self._stats_widget)
        layout.addStretch()

        # Settings button
        btn_settings = QPushButton("⚙  Settings")
        btn_settings.setToolTip("Open application settings")
        btn_settings.clicked.connect(self._open_settings)
        layout.addWidget(btn_settings)

        # Connect Enter in any field to search
        for field in (self._query, self._date_from, self._date_to,
                      self._camera, self._obj, self._person):
            field.returnPressed.connect(self._emit_search)

        self._load_completers()
        self._load_stats()

    def _load_completers(self):
        """Populate autocomplete lists for camera, object, and person fields from the database."""
        self._camera.setCompleter(_make_completer(self._db.get_distinct_cameras()))
        self._obj.setCompleter(_make_completer(self._db.get_distinct_objects()))
        # starts_with=True: 'Esa' does not suggest 'Vesa'
        self._person.setCompleter(_make_completer(self._db.get_distinct_persons(), starts_with=True))

    def _load_stats(self):
        """Load and display all stats sections."""
        # Basic stats
        s = self._db.stats()
        total = s.get("total_images", 0)
        oldest, newest = self._db.get_date_range()

        def short(d: str) -> str:
            return d[:10] if d else "?"

        date_range = f"{short(oldest)} – {short(newest)}" if oldest or newest else "no dates"
        self._basic_stats.setText(f"📊 {total} images\n📅 {date_range}")

        # Top cameras
        cameras = self._db.get_top_cameras(5)
        if cameras:
            lines = [f"  • {name}: {count}" for name, count in cameras]
            self._top_cameras.setText("📷 Top cameras:\n" + "\n".join(lines))
        else:
            self._top_cameras.setText("📷 No camera data")

        # Top objects
        objects = self._db.get_top_objects(5)
        if objects:
            lines = [f"  • {name}: {count}" for name, count in objects]
            self._top_objects.setText("🎯 Top objects:\n" + "\n".join(lines))
        else:
            self._top_objects.setText("🎯 No object data")

        # Top persons
        persons = self._db.get_top_persons(5)
        if persons:
            lines = [f"  • {name}: {count}" for name, count in persons]
            self._top_persons.setText("👤 Top people:\n" + "\n".join(lines))
        else:
            self._top_persons.setText("👤 No person data")

        # Top locations
        locations = self._db.get_top_locations(5)
        if locations:
            lines = [f"  • {coords}: {count}" for coords, count in locations]
            self._top_locations.setText("📍 Top locations:\n" + "\n".join(lines))
        else:
            self._top_locations.setText("📍 No location data")

    def refresh(self):
        """Reload completers and stats (call after new indexing)."""
        self._load_completers()
        self._load_stats()

    def _emit_search(self):
        """Parse all filter fields and emit the search_requested signal."""
        parsed = _parse_query(self._query.text())
        self.search_requested.emit({
            "query":      self._query.text().strip(),
            "query_and":  parsed["and_terms"],
            "query_or":   parsed["or_terms"],
            "query_mode": parsed["mode"],
            "date_from":  self._date_from.text().strip(),
            "date_to":    self._date_to.text().strip(),
            "camera":     self._camera.text().strip(),
            "obj":        self._obj.text().strip(),
            "person":     self._person.text().strip(),
            "limit":      self._limit.value(),
        })

    def _clear(self):
        """Clear all filter fields and emit an empty search to reset the thumbnail grid."""
        for field in (self._query, self._date_from, self._date_to,
                      self._camera, self._obj, self._person):
            field.clear()
        self.search_requested.emit({
            "query": "", "query_and": [], "query_or": [], "query_mode": "and",
            "date_from": "", "date_to": "", "camera": "", "obj": "", "person": "",
            "limit": self._limit.value(),
        })

    def _open_settings(self):
        """Open the settings dialog modally."""
        from src.gui.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self._db, self._config, parent=self)
        dlg.exec()


def _parse_query(raw: str) -> dict:
    """Parse the free-text search field into AND or OR term lists.

    Syntax:
      "Jari & dog"   -> AND: all terms must be found in the image
      "Jari, Vesa"   -> OR:  any one term is sufficient
      "dog"          -> single term (treated as AND with one element)

    & takes precedence if both separators appear in the same query.
    """
    raw = raw.strip()
    if "&" in raw:
        terms = [t.strip() for t in raw.split("&") if t.strip()]
        return {"and_terms": terms, "or_terms": [], "mode": "and"}
    if "," in raw:
        terms = [t.strip() for t in raw.split(",") if t.strip()]
        return {"and_terms": [], "or_terms": terms, "mode": "or"}
    if raw:
        return {"and_terms": [raw], "or_terms": [], "mode": "and"}
    return {"and_terms": [], "or_terms": [], "mode": "and"}
