"""Settings dialog — reads AppConfig, writes config.local.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from PyQt6.QtCore import Qt, QProcess
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QMessageBox,
    QProgressBar,
    QTreeWidget,
    QHeaderView,
    QTreeWidgetItem,
)

if TYPE_CHECKING:
    from src.config import AppConfig

CONFIG_LOCAL = Path(__file__).parent.parent.parent / "config.local.yaml"

if TYPE_CHECKING:
    from src.database import Database



class FacesViewDialog(QDialog):
    """Dialog showing all known persons and their face detection counts from the DB."""

    def __init__(self, db: "Database", parent=None):
        super().__init__(parent)
        self._db = db
        self.setWindowTitle("Stored Face Identities")
        self.setMinimumSize(480, 420)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Known persons in database (from face detection stage):"))

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Person", "Detections"])
        # Explicit alternating colors for dark theme readability
        self._tree.setStyleSheet("""
            QTreeWidget { color: #cdd6f4; background: #1e1e2e; }
            QTreeWidget::item { padding: 4px; }
            QTreeWidget::item:alternate { background: #181825; }
            QTreeWidget::item:selected { background: #313244; color: #cdd6f4; }
            QTreeWidget::item:hover { background: #45475a; }
            QHeaderView::section { background: #313244; color: #cdd6f4; padding: 4px; }
        """)
        self._tree.setAlternatingRowColors(True)
        layout.addWidget(self._tree)

        # Info panel shown when a person is selected
        layout.addWidget(QLabel("<b>Appearances:</b>"))
        self._info = QTextEdit()
        self._info.setReadOnly(True)
        self._info.setMaximumHeight(120)
        self._info.setStyleSheet("font-size: 11px;")
        self._info.setPlaceholderText("Select a person to see which images they appear in…")
        layout.addWidget(self._info)

        self._populate()
        self._tree.itemSelectionChanged.connect(self._on_selection_changed)

        btn = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn.rejected.connect(self.reject)
        layout.addWidget(btn)

    def _populate(self):
        """Fill the tree with all known persons and their detection counts."""
        persons = self._db.get_distinct_persons()
        with self._db._conn() as conn:
            for name in persons:
                count = conn.execute(
                    "SELECT COUNT(*) FROM face_detections WHERE person_name = ?", (name,)
                ).fetchone()[0]
                item = QTreeWidgetItem(self._tree)
                item.setText(0, name)
                item.setText(1, str(count))
        self._tree.resizeColumnToContents(0)
        self._tree.resizeColumnToContents(1)

    def _on_selection_changed(self):
        """Show detection details for the currently selected person."""
        items = self._tree.selectedItems()
        if not items:
            self._info.clear()
            return
        name = items[0].text(0)
        with self._db._conn() as conn:
            rows = conn.execute(
                """SELECT i.file_path, fd.confidence, fd.bbox_x1, fd.bbox_y1, fd.bbox_x2, fd.bbox_y2
                   FROM face_detections fd
                   JOIN images i ON fd.image_id = i.id
                   WHERE fd.person_name = ?
                   ORDER BY fd.confidence DESC""",
                (name,)
            ).fetchall()
        if not rows:
            self._info.setPlainText("No detections found.")
            return
        lines = [f"{name} — {len(rows)} detection(s):"]
        for path, conf, x1, y1, x2, y2 in rows[:10]:
            lines.append(f"  • {path}  (conf {conf:.2f}, bbox [{int(x1)},{int(y1)},{int(x2)},{int(y2)}])")
        if len(rows) > 10:
            lines.append(f"  … and {len(rows) - 10} more")
        self._info.setPlainText("\n".join(lines))


class CleanupDialog(QDialog):
    """Dialog for removing orphaned database entries whose source files are gone."""

    def __init__(self, db: "Database", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Clean Up Orphaned Entries")
        self.setMinimumSize(600, 400)

        self._db = db
        self._setup_ui()

    def _setup_ui(self):
        """Build the cleanup dialog layout with directory input, preview tree, and action buttons."""
        layout = QVBoxLayout(self)

        # Input field for directory to clean
        self._dir_input = QLineEdit()
        self._dir_input.setPlaceholderText("Enter directory to clean (e.g., /home/user/Pictures)")
        layout.addWidget(self._dir_input)

        # Button to browse
        btn_browse = QPushButton("Browse…")
        btn_browse.clicked.connect(self._browse_dir)
        layout.addWidget(btn_browse)

        # Preview section
        self._preview_label = QLabel("Preview of entries to be deleted:")
        layout.addWidget(self._preview_label)

        self._preview_tree = QTreeWidget()
        self._preview_tree.setHeaderLabels(["Table", "Field", "Value"])
        self._preview_tree.setColumnWidth(0, 150)
        self._preview_tree.setColumnWidth(1, 150)
        self._preview_tree.setColumnWidth(2, 200)
        self._preview_tree.setAlternatingRowColors(True)
        self._preview_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self._preview_tree)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._confirm_cleanup)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Populate preview on init
        self._populate_preview()

    def _browse_dir(self):
        """Open a directory picker and update the input field and preview."""
        d = QFileDialog.getExistingDirectory(self, "Select directory to clean")
        if d:
            self._dir_input.setText(d)
            self._populate_preview()

    def _populate_preview(self):
        """Query the database for entries under the entered directory and display them."""
        dir_path = self._dir_input.text().strip()
        if not dir_path:
            self._preview_tree.clear()
            return

        try:
            paths = self._db.get_file_paths_by_prefix(dir_path)
            self._preview_tree.clear()
            for path in paths:
                item = QTreeWidgetItem(self._preview_tree)
                item.setText(0, "images")
                item.setText(1, "file_path")
                item.setText(2, path)
            self._preview_label.setText(f"Found {len(paths)} entries under '{dir_path}'")
        except Exception as e:
            self._preview_label.setText(f"Error: {e}")

    def _confirm_cleanup(self):
        """Ask for confirmation, then delete all database entries under the selected directory."""
        dir_path = self._dir_input.text().strip()
        if not dir_path:
            QMessageBox.warning(self, "Warning", "No directory selected!")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Cleanup",
            f"Are you sure you want to delete all entries referencing '{dir_path}'?\n\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._cleanup_database(dir_path)
        else:
            self.reject()

    def _cleanup_database(self, dir_path):
        """Delete all images and related data whose paths begin with dir_path."""
        try:
            deleted = self._db.delete_images_by_path_prefix(dir_path)
            if deleted == 0:
                QMessageBox.information(self, "No entries found", "No entries to clean.")
                return
            QMessageBox.information(self, "Success", f"Cleaned {deleted} entries from '{dir_path}'.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Cleanup failed: {e}")


class SettingsDialog(QDialog):
    """Modal dialog for editing all AppConfig settings."""

    def __init__(self, db: Database, config: AppConfig, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(540, 460)
        self._db = db
        self._config = config

        layout = QVBoxLayout(self)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._make_general_tab(), "General")
        self._tabs.addTab(self._make_yolo_tab(), "YOLO")
        self._tabs.addTab(self._make_faces_tab(), "Faces")
        self._tabs.addTab(self._make_llm_tab(), "LLM")
        self._tabs.addTab(self._make_database_tab(), "Database")
        self._tabs.addTab(self._make_processing_tab(), "Processing")
        layout.addWidget(self._tabs)

        self._status = QLabel()
        self._status.setStyleSheet("font-size: 11px;")
        layout.addWidget(self._status)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.Apply,
        )
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._save)
        layout.addWidget(buttons)

    # ------------------------------------------------------------------ tabs

    def _make_general_tab(self) -> QWidget:
        """Build the General tab with image directory list and extensions field."""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(6)

        layout.addWidget(QLabel("Image directories (one per line):"))

        self._dirs_list = QListWidget()
        self._dirs_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        for d in self._config.image_dirs:
            self._dirs_list.addItem(d)
        layout.addWidget(self._dirs_list)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("Add…")
        btn_add.clicked.connect(self._add_dir)
        btn_remove = QPushButton("Remove selected")
        btn_remove.clicked.connect(self._remove_dir)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_remove)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        form = QFormLayout()
        self._extensions = QLineEdit(", ".join(self._config.extensions))
        self._extensions.setToolTip("Comma-separated file extensions, e.g. .jpg, .png")
        form.addRow("Supported extensions:", self._extensions)
        layout.addLayout(form)
        return w

    def _make_yolo_tab(self) -> QWidget:
        """Build the YOLO tab with model path, confidence, and device controls."""
        w = QWidget()
        form = QFormLayout(w)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        model_row = QHBoxLayout()
        self._yolo_model = QLineEdit(str(self._config.yolo.model))
        btn = QPushButton("Browse…")
        btn.clicked.connect(lambda: self._browse_file(
            self._yolo_model, "Model weights (*.pt *.onnx)"))
        model_row.addWidget(self._yolo_model)
        model_row.addWidget(btn)
        form.addRow("Model file:", model_row)

        self._yolo_conf = QDoubleSpinBox()
        self._yolo_conf.setRange(0.05, 0.99)
        self._yolo_conf.setSingleStep(0.05)
        self._yolo_conf.setDecimals(2)
        self._yolo_conf.setValue(float(self._config.yolo.confidence))
        self._yolo_conf.setToolTip("Minimum detection confidence (0.05–0.99)")
        form.addRow("Confidence threshold:", self._yolo_conf)

        from PyQt6.QtWidgets import QComboBox
        self._yolo_device = QComboBox()
        self._yolo_device.addItems(["GPU 0", "GPU 1", "CPU"])
        dev = str(self._config.yolo.device).lower()
        self._yolo_device.setCurrentIndex({"0": 0, "1": 1, "cpu": 2}.get(dev, 0))
        self._yolo_device.setToolTip("Which device to run YOLO on")
        form.addRow("Device:", self._yolo_device)

        self._yolo_info = QLabel("Model info loads when YOLO runs.")
        self._yolo_info.setStyleSheet("font-size: 11px; color: #a6adc8;")
        self._yolo_info.setWordWrap(True)
        form.addRow("Model info:", self._yolo_info)

        self._try_load_yolo_info()

        return w

    def _try_load_yolo_info(self):
        """Attempt to load the configured YOLO model and display its class count and task type."""
        try:
            from ultralytics import YOLO
            model_path = self._yolo_model.text()
            if model_path:
                m = YOLO(model_path)
                names = m.names
                n_classes = len(names) if names else "?"
                task = getattr(m, 'task', 'detect')
                self._yolo_info.setText(
                    f"Classes: {n_classes} | Task: {task} | "
                    f"Sample: {', '.join(list(names.values())[:5])}…"
                )
        except Exception as e:
            self._yolo_info.setText(f"(Could not load model info: {e})")

    def _make_faces_tab(self) -> QWidget:
        """Build the Faces tab with reference directory, threshold, and model controls."""
        w = QWidget()
        form = QFormLayout(w)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        ref_row = QHBoxLayout()
        self._faces_ref = QLineEdit(self._config.faces.reference_dir)
        btn = QPushButton("Browse…")
        btn.clicked.connect(lambda: self._browse_dir(self._faces_ref))
        ref_row.addWidget(self._faces_ref)
        ref_row.addWidget(btn)
        form.addRow("Reference photos dir:", ref_row)
        form.addRow(QLabel(
            "  Place photos as  data/faces/<Name>/*.jpg\n"
            "  Re-run the 'faces' stage after changes."
        ))

        self._faces_threshold = QDoubleSpinBox()
        self._faces_threshold.setRange(0.10, 0.99)
        self._faces_threshold.setSingleStep(0.05)
        self._faces_threshold.setDecimals(2)
        self._faces_threshold.setValue(float(self._config.faces.similarity_threshold))
        self._faces_threshold.setToolTip("Lower value = stricter matching")
        form.addRow("Similarity threshold:", self._faces_threshold)

        self._faces_model = QLineEdit(self._config.faces.model)
        self._faces_model.setToolTip("InsightFace model name, e.g. buffalo_l or buffalo_s")
        form.addRow("InsightFace model:", self._faces_model)

        btn_show_faces = QPushButton("👤 Show stored faces…")
        btn_show_faces.clicked.connect(self._open_faces_dialog)
        form.addRow("", btn_show_faces)

        return w

    def _open_faces_dialog(self):
        """Open the FacesViewDialog to inspect stored face identities."""
        dlg = FacesViewDialog(self._db, self)
        dlg.exec()

    def _make_llm_tab(self) -> QWidget:
        """Build the LLM tab with API URL, model, prompt, and inference controls."""
        w = QWidget()
        form = QFormLayout(w)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        self._llm_url = QLineEdit(self._config.llm.api_url)
        self._llm_url.setToolTip("LM Studio: http://localhost:1234/v1/chat/completions")
        form.addRow("API URL:", self._llm_url)

        self._llm_model = QLineEdit(self._config.llm.model)
        self._llm_model.setToolTip("Model name exactly as shown in LM Studio")
        form.addRow("Model name:", self._llm_model)

        self._llm_prompt = QTextEdit()
        self._llm_prompt.setPlainText(self._config.llm.prompt)
        self._llm_prompt.setFixedHeight(110)
        self._llm_prompt.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        form.addRow("Prompt:", self._llm_prompt)

        self._llm_timeout = QSpinBox()
        self._llm_timeout.setRange(10, 600)
        self._llm_timeout.setSuffix(" s")
        self._llm_timeout.setValue(self._config.llm.timeout)
        form.addRow("Timeout:", self._llm_timeout)

        self._llm_retries = QSpinBox()
        self._llm_retries.setRange(0, 10)
        self._llm_retries.setValue(self._config.llm.max_retries)
        form.addRow("Max retries:", self._llm_retries)

        self._llm_max_tokens = QSpinBox()
        self._llm_max_tokens.setRange(64, 4096)
        self._llm_max_tokens.setValue(getattr(self._config.llm, 'max_tokens', 512))
        form.addRow("Max tokens:", self._llm_max_tokens)

        self._llm_image_side = QSpinBox()
        self._llm_image_side.setRange(128, 1024)
        self._llm_image_side.setSingleStep(64)
        self._llm_image_side.setValue(getattr(self._config.llm, 'image_max_side', 512))
        self._llm_image_side.setToolTip("Longest side in pixels before sending to LLM")
        form.addRow("Image resize (px):", self._llm_image_side)

        self._llm_threads = QSpinBox()
        self._llm_threads.setRange(1, 4)
        self._llm_threads.setValue(getattr(self._config.llm, 'threads', 1))
        self._llm_threads.setToolTip("Parallel LLM requests (1–4)")
        form.addRow("LLM threads:", self._llm_threads)

        return w

    def _make_database_tab(self) -> QWidget:
        """Build the Database tab with status info, path, secondary dirs, S&R, and maintenance."""
        from PyQt6.QtWidgets import QScrollArea
        outer = QWidget()
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        outer_layout.addWidget(scroll)

        w = QWidget()
        scroll.setWidget(w)
        layout = QVBoxLayout(w)
        layout.setSpacing(6)

        # 1. Tietokannan tiedot -osio
        layout.addWidget(QLabel("<b>Current database status</b>"))


        info_form = QFormLayout()
        info_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.lbl_db_path = QLabel(self._config.database_path)
        info_form.addRow("Path:", self.lbl_db_path)

        size_bytes = self._db.db_size()
        size_mb = size_bytes / (1024 * 1024)
        size_text = f"{size_mb:,.1f} MB ({size_bytes:,} bytes)"
        self.lbl_db_size = QLabel(size_text)
        info_form.addRow("File size:", self.lbl_db_size)

        stats = self._db.stats()
        c = stats.get("completed", {})

        self.lbl_image_count = QLabel(
            f"Total: {stats.get('total_images', 0)}, "
            f"exif: {c.get('exif', 0)}, "
            f"yolo: {c.get('yolo', 0)}, "
            f"faces: {c.get('faces', 0)}, "
            f"llm: {c.get('llm', 0)}"
        )

        info_form.addRow("Images:", self.lbl_image_count)

        layout.addLayout(info_form)

        # 2. Database file -muokkaus
        layout.addWidget(QLabel("<b>Database location</b>"))
        db_row = QHBoxLayout()
        self._db_path = QLineEdit(self._config.database_path)
        btn_db = QPushButton("Browse…")
        btn_db.clicked.connect(self._browse_db)
        db_row.addWidget(self._db_path)
        db_row.addWidget(btn_db)
        layout.addLayout(db_row)

        # 3. Secondary image directories
        layout.addWidget(QLabel("<b>Secondary image directories</b>"))
        layout.addWidget(QLabel(
            "If images have moved, add the new root directory here.\n"
            "The viewer will look here when the primary path is missing."
        ))

        self._secondary_dirs_list = QListWidget()
        for d in self._db.get_secondary_dirs():
            self._secondary_dirs_list.addItem(d)
        self._secondary_dirs_list.setMaximumHeight(100)
        layout.addWidget(self._secondary_dirs_list)

        sec_btn_row = QHBoxLayout()
        btn_add_sec = QPushButton("Add…")
        btn_add_sec.clicked.connect(self._add_secondary_dir)
        btn_remove_sec = QPushButton("Remove selected")
        btn_remove_sec.clicked.connect(self._remove_secondary_dir)
        sec_btn_row.addWidget(btn_add_sec)
        sec_btn_row.addWidget(btn_remove_sec)
        sec_btn_row.addStretch()
        layout.addLayout(sec_btn_row)

        # 4. LLM search & replace
        layout.addWidget(QLabel("<b>LLM description search & replace</b>"))
        layout.addWidget(QLabel("Fix LM Studio artifacts in existing descriptions."))

        sr_form = QFormLayout()
        self._sr_search = QLineEdit()
        self._sr_search.setPlaceholderText("Text to find…")
        self._sr_replace = QLineEdit()
        self._sr_replace.setPlaceholderText("Replace with…")
        sr_form.addRow("Find:", self._sr_search)
        sr_form.addRow("Replace:", self._sr_replace)
        layout.addLayout(sr_form)

        sr_btn_row = QHBoxLayout()
        btn_sr_preview = QPushButton("Preview matches")
        btn_sr_apply = QPushButton("Apply to all")
        btn_sr_preview.clicked.connect(self._sr_preview)
        btn_sr_apply.clicked.connect(self._sr_apply)
        sr_btn_row.addWidget(btn_sr_preview)
        sr_btn_row.addWidget(btn_sr_apply)
        sr_btn_row.addStretch()
        layout.addLayout(sr_btn_row)

        self._sr_result_label = QLabel()
        self._sr_result_label.setStyleSheet("font-size: 11px;")
        layout.addWidget(self._sr_result_label)

        # 5. Maintenance actions
        layout.addWidget(QLabel("<b>Maintenance actions</b>"))
        maintenance_row = QHBoxLayout()
        maintenance_row.setSpacing(8)

        layout.addLayout(maintenance_row)
        btn_backup = QPushButton("Create backup…")
        btn_backup.clicked.connect(self._backup_db)
        maintenance_row.addWidget(btn_backup)

        # ... cleanup ym nappi ...
        cleanup_row = QHBoxLayout()
        btn_cleanup = QPushButton("Clean up orphaned / invalid entries…")
        btn_cleanup.clicked.connect(self._open_cleanup_dialog)
        cleanup_row.addWidget(btn_cleanup)

        btn_clear_raw_json = QPushButton("Clear raw EXIF cache")
        btn_clear_raw_json.setToolTip(
            "Tyhjentää exif_data.raw_json-kentän kaikista riveistä.\n"
            "Kenttä tallentaa raaka-EXIFin JSON-muodossa ja voi kasvaa useita gigatavuja.\n"
            "Kaikki oleellinen EXIF-data on jo omissa kolumneissaan."
        )
        btn_clear_raw_json.clicked.connect(self._clear_raw_json)
        cleanup_row.addWidget(btn_clear_raw_json)

        cleanup_row.addStretch()

        btn_vacuum = QPushButton("VACUUM / Optimize")
        btn_vacuum.clicked.connect(self._run_vacuum)
        maintenance_row.addWidget(btn_vacuum)

        btn_reindex = QPushButton("Rebuild indexes")
        btn_reindex.clicked.connect(self._rebuild_indexes)
        maintenance_row.addWidget(btn_reindex)

        maintenance_row.addStretch()


        layout.addLayout(cleanup_row)

        return outer


    def _make_processing_tab(self) -> QWidget:
        """Build the Processing tab with batch settings, CUDA info, and pipeline stage buttons."""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(8)

        form = QFormLayout()

        self._proc_skip = QCheckBox()
        self._proc_skip.setChecked(self._config.processing.skip_existing)
        self._proc_skip.setText(
            "Skip already-processed images" if self._config.processing.skip_existing
            else "Do not skip — re-process all images"
        )
        self._proc_skip.stateChanged.connect(self._on_proc_skip_changed)
        form.addRow("", self._proc_skip)

        self._proc_batch = QSpinBox()
        self._proc_batch.setRange(1, 1000)
        self._proc_batch.setValue(self._config.processing.batch_size)
        form.addRow("Batch size:", self._proc_batch)

        self._proc_workers = QSpinBox()
        self._proc_workers.setRange(1, 16)
        self._proc_workers.setValue(self._config.processing.max_workers)
        self._proc_workers.setToolTip("Parallel threads for EXIF/file reads")
        form.addRow("Max workers:", self._proc_workers)

        self._proc_limit = QSpinBox()
        self._proc_limit.setRange(0, 999999)
        self._proc_limit.setValue(0)
        self._proc_limit.setSpecialValueText("All")
        self._proc_limit.setToolTip("0 = process all; set N to limit for testing")
        form.addRow("Limit (testing):", self._proc_limit)

        layout.addLayout(form)
        layout.addSpacing(8)

        self._cuda_label = QLabel()
        self._cuda_label.setStyleSheet("font-size: 11px;")
        layout.addWidget(self._cuda_label)
        self._check_cuda()

        layout.addWidget(QLabel("<b>Pipeline stages</b> (only one at a time):"))

        btn_grid = QHBoxLayout()
        btn_grid.setSpacing(6)

        self._stage_buttons = {}
        for label, stage in [("📁 Scan Images", "scan"), ("📷 Scan EXIF", "exif"),
                              ("👤 Learn & Identify Faces", "faces"), ("🤖 Start LLM Vision", "llm")]:
            btn = QPushButton(label)
            btn.setCheckable(False)
            btn.setEnabled(True)
            btn.clicked.connect(lambda checked, s=stage: self._run_pipeline_stage(s))
            btn_grid.addWidget(btn)
            self._stage_buttons[stage] = btn

        layout.addLayout(btn_grid)
        layout.addSpacing(8)

        # Check LM Studio availability and disable button if not running
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self._check_llm_availability)

        self._proc_progress = QProgressBar()
        self._proc_progress.setVisible(False)
        self._proc_progress.setRange(0, 100)
        layout.addWidget(self._proc_progress)

        self._proc_status_label = QLabel("")
        self._proc_status_label.setStyleSheet("font-size: 11px;")
        layout.addWidget(self._proc_status_label)

        self._proc_cancel_btn = QPushButton("✕ Cancel")
        self._proc_cancel_btn.setVisible(False)
        self._proc_cancel_btn.clicked.connect(self._cancel_pipeline)
        layout.addWidget(self._proc_cancel_btn)

        layout.addStretch()
        return w

    def _on_proc_skip_changed(self, state: int):
        """Update the skip checkbox label to reflect the current checked state."""
        self._proc_skip.setText(
            "Skip already-processed images" if state else "Do not skip — re-process all images"
        )

    def _get_system_cuda_version(self) -> str | None:
        """Return system CUDA version string from nvidia-smi, or None."""
        try:
            import subprocess
            result = subprocess.run(["nvidia-smi"], capture_output=True, text=True, timeout=5)
            for line in result.stdout.splitlines():
                if "CUDA Version" in line:
                    return line.split("CUDA Version:")[-1].strip().split()[0]
        except Exception:
            pass
        return None

    def _check_cuda(self):
        """Detect CUDA availability via PyTorch and update the status label."""
        try:
            import torch
            if torch.cuda.is_available():
                dev_name = torch.cuda.get_device_name(0)
                system_cuda = self._get_system_cuda_version()
                if system_cuda:
                    cuda_info = f"system CUDA {system_cuda}"
                else:
                    cuda_info = f"torch CUDA {torch.version.cuda}"
                self._cuda_label.setText(f"✅ CUDA available: {dev_name} ({cuda_info})")
                self._cuda_label.setStyleSheet("font-size: 11px; color: #a6e3a1;")
            else:
                self._cuda_label.setText("⚠️ CUDA not available — pipeline stages will run on CPU (slow).")
                self._cuda_label.setStyleSheet("font-size: 11px; color: #f9e2af;")
        except ImportError:
            self._cuda_label.setText("⚠️ PyTorch not found — cannot check CUDA.")
            self._cuda_label.setStyleSheet("font-size: 11px; color: #f38ba8;")

    def _check_llm_availability(self):
        """Synchronous socket check — fast on localhost (connect refused = instant)."""
        import socket
        from urllib.parse import urlparse

        btn = self._stage_buttons.get("llm")
        if not btn:
            return

        api_url = getattr(self._config.llm, 'api_url', 'http://localhost:1234/v1/chat/completions')
        try:
            parsed = urlparse(api_url)
            host = parsed.hostname or 'localhost'
            port = parsed.port or 80
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.0)
            result = sock.connect_ex((host, port))
            sock.close()
            available = (result == 0)
        except Exception:
            available = False

        btn.setEnabled(available)
        if not available:
            btn.setToolTip(f"LM Studio is not running at {api_url}\nStart LM Studio and reopen Settings.")
        else:
            btn.setToolTip("")

    def _run_pipeline_stage(self, stage: str):
        """Launch a pipeline stage as a subprocess."""
        import sys
        import shlex

        for btn in self._stage_buttons.values():
            btn.setEnabled(False)
        self._proc_cancel_btn.setVisible(True)
        self._proc_progress.setVisible(True)
        self._proc_progress.setRange(0, 0)
        self._proc_status_label.setText(f"Running stage: {stage}…")

        limit = self._proc_limit.value()
        cmd = [sys.executable, "-m", "src.main", "--stage", stage]
        if limit > 0:
            cmd += ["--limit", str(limit)]
        if not self._proc_skip.isChecked():
            cmd += ["--force"]

        self._proc_status_label.setText(f"Command: {shlex.join(cmd)}")

        self._qprocess = QProcess(self)
        self._qprocess.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._qprocess.readyRead.connect(self._on_proc_output)
        self._qprocess.finished.connect(lambda code, status: self._on_proc_finished(stage, code))
        self._qprocess.start(cmd[0], cmd[1:])

    def _on_proc_output(self):
        """Read subprocess stdout and display the last non-empty line in the status label."""
        data = bytes(self._qprocess.readAll()).decode("utf-8", errors="replace")
        lines = [l.strip() for l in data.splitlines() if l.strip()]
        if lines:
            self._proc_status_label.setText(lines[-1])

    def _on_proc_finished(self, stage: str, exit_code: int):
        """Handle subprocess completion: re-enable buttons and update status."""
        self._proc_progress.setRange(0, 100)
        self._proc_progress.setValue(100)
        self._proc_cancel_btn.setVisible(False)
        for s, btn in self._stage_buttons.items():
            btn.setEnabled(True)
        # Re-check LLM availability after stage completes
        self._check_llm_availability()
        if exit_code == 0:
            self._proc_status_label.setText(f"✅ Stage '{stage}' completed successfully.")
            self._set_status(f"Stage '{stage}' done.", error=False)
        else:
            self._proc_status_label.setText(f"❌ Stage '{stage}' exited with code {exit_code}.")
            self._set_status(f"Stage '{stage}' failed (exit {exit_code}).", error=True)

    def _cancel_pipeline(self):
        """Kill the running pipeline subprocess and re-enable the stage buttons."""
        if hasattr(self, '_qprocess') and self._qprocess:
            self._qprocess.kill()
            self._proc_status_label.setText("Process cancelled.")
        self._proc_cancel_btn.setVisible(False)
        for btn in self._stage_buttons.values():
            btn.setEnabled(True)
        self._proc_progress.setVisible(False)
        self._check_llm_availability()

    def _add_secondary_dir(self):
        """Open a directory picker and persist the selected secondary image directory."""
        d = QFileDialog.getExistingDirectory(self, "Select secondary image directory")
        if d:
            self._db.add_secondary_dir(d)
            self._secondary_dirs_list.addItem(d)

    def _remove_secondary_dir(self):
        """Remove the selected secondary directory from the database and the list widget."""
        for item in self._secondary_dirs_list.selectedItems():
            self._db.remove_secondary_dir(item.text())
            self._secondary_dirs_list.takeItem(self._secondary_dirs_list.row(item))

    def _sr_preview(self):
        """Count and display how many LLM descriptions contain the search string."""
        needle = self._sr_search.text()
        if not needle:
            self._sr_result_label.setText("Enter search text first.")
            return
        with self._db._conn() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM llm_descriptions WHERE description LIKE ?",
                (f"%{needle}%",)
            ).fetchone()[0]
        self._sr_result_label.setText(f"Found {count} descriptions containing '{needle}'.")

    def _sr_apply(self):
        """Replace all occurrences of the search string in LLM descriptions after confirmation."""
        needle = self._sr_search.text()
        replacement = self._sr_replace.text()
        if not needle:
            self._sr_result_label.setText("Enter search text first.")
            return
        reply = QMessageBox.question(
            self, "Confirm Replace",
            f"Replace all occurrences of:\n  '{needle}'\nwith:\n  '{replacement}'\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        with self._db._conn() as conn:
            conn.execute(
                "UPDATE llm_descriptions SET description = REPLACE(description, ?, ?)",
                (needle, replacement)
            )
        self._sr_result_label.setText(f"Done. Replaced all occurrences of '{needle}'.")

    # Database maint.

    def _backup_db(self):
        """Copy the current database file to a user-selected backup path."""
        # Get the current database path
        current_db_path = self._db_path.text()
        if not current_db_path:
            self._set_status("No database file selected.", error=True)
            return

        # Open file dialog to let user choose backup destination
        backup_path, _ = QFileDialog.getSaveFileName(
            self, "Backup Database", current_db_path + ".bak", "SQLite (*.db)"
        )
        if not backup_path:
            return

        try:
            import shutil
            shutil.copy2(current_db_path, backup_path)
            self._set_status(f"Database backed up to {backup_path}")
        except Exception as e:
            self._set_status(f"Error backing up database: {e}", error=True)

    def _run_vacuum(self):
        """Run VACUUM on the current SQLite database to reclaim space."""
        db_path = self._db_path.text()
        if not db_path:
            self._set_status("No database file selected. Cannot run VACUUM.", error=True)
            return

        reply = QMessageBox.question(
            self,
            "Confirm Vacuum",
            "Running VACUUM will optimize the database and may take some time.\n\nAre you sure?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            self._set_status("VACUUM canceled.")
            return

        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            conn.execute("VACUUM;")
            conn.close()
            self._set_status("Database vacuumed successfully!")
        except Exception as e:
            self._set_status(f"Error running VACUUM: {e}", error=True)

    def _rebuild_indexes(self):
        """Rebuild all database indexes to optimize query performance."""
        db_path = self._db_path.text()
        if not db_path:
            self._set_status("No database file selected. Cannot rebuild indexes.", error=True)
            return

        reply = QMessageBox.question(
            self,
            "Confirm Rebuild Indexes",
            "This will rebuild all database indexes. It may take a while.\n\nAre you sure?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            self._set_status("Index rebuild canceled.")
            return

        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            for (table,) in cursor.fetchall():
                cursor.execute(f"REINDEX {table};")
            conn.commit()
            conn.close()
            self._set_status("All indexes rebuilt successfully!")
        except Exception as e:
            self._set_status(f"Error rebuilding indexes: {e}", error=True)

    def _clear_raw_json(self):
        """Set exif_data.raw_json to NULL on all rows to free disk space."""
        with self._db._conn() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM exif_data WHERE raw_json IS NOT NULL"
            ).fetchone()[0]

        if count == 0:
            QMessageBox.information(self, "Clear raw EXIF cache", "raw_json on jo tyhjä kaikissa riveissä.")
            return

        reply = QMessageBox.question(
            self,
            "Clear raw EXIF cache",
            f"Tyhjennetään raw_json {count} riviltä.\n\n"
            "Kaikki oleellinen EXIF-data (kamera, päivämäärä, GPS jne.) säilyy omissa kolumneissaan.\n\n"
            "Aja tämän jälkeen VACUUM vapauttaaksesi levytilan.\n\n"
            "Jatketaanko?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            with self._db._conn() as conn:
                conn.execute("UPDATE exif_data SET raw_json = NULL")
            self._set_status(f"raw_json tyhjennetty {count} riviltä. Aja VACUUM vapauttaaksesi levytilan.")
        except Exception as e:
            self._set_status(f"Virhe: {e}", error=True)

    def _open_cleanup_dialog(self):
        """Open the CleanupDialog to remove orphaned database entries."""
        dlg = CleanupDialog(self._db, self)
        dlg.exec()
    # ------------------------------------------------------------------ helpers

    def _add_dir(self):
        """Open a directory picker and add the selection to the image directories list."""
        d = QFileDialog.getExistingDirectory(
            self, "Select image directory",
            self._dirs_list.item(0).text() if self._dirs_list.count() else "",
        )
        if d and not self._dir_exists(d):
            self._dirs_list.addItem(d)

    def _dir_exists(self, path: str) -> bool:
        """Return True if path is already present in the image directories list."""
        for i in range(self._dirs_list.count()):
            if self._dirs_list.item(i).text() == path:
                return True
        return False

    def _remove_dir(self):
        """Remove the selected image directory from the list."""
        for item in self._dirs_list.selectedItems():
            self._dirs_list.takeItem(self._dirs_list.row(item))

    def _browse_db(self):
        """Open a file picker to choose the database file path."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Database file", self._db_path.text(), "SQLite (*.db)")
        if path:
            self._db_path.setText(path)

    def _browse_file(self, field: QLineEdit, file_filter: str):
        """Open a file picker and update field with the selected path."""
        path, _ = QFileDialog.getOpenFileName(self, "Select file", field.text(), file_filter)
        if path:
            field.setText(path)

    def _browse_dir(self, field: QLineEdit):
        """Open a directory picker and update field with the selected path."""
        d = QFileDialog.getExistingDirectory(self, "Select directory", field.text())
        if d:
            field.setText(d)



    # ------------------------------------------------------------------ save

    def _collect(self) -> dict:
        """Collect all widget values into a YAML-ready dict."""
        dirs = [self._dirs_list.item(i).text() for i in range(self._dirs_list.count())]
        exts = [e.strip() for e in self._extensions.text().split(",") if e.strip()]
        device_map = {0: 0, 1: 1, 2: "cpu"}
        return {
            "image_dirs": dirs,
            "extensions": exts,
            "database": {"path": self._db_path.text()},
            "yolo": {
                "model": self._yolo_model.text(),
                "confidence": round(self._yolo_conf.value(), 2),
                "device": device_map[self._yolo_device.currentIndex()],
            },
            "faces": {
                "reference_dir": self._faces_ref.text(),
                "similarity_threshold": round(self._faces_threshold.value(), 2),
                "model": self._faces_model.text(),
            },
            "llm": {
                "api_url": self._llm_url.text().strip(),
                "model": self._llm_model.text().strip(),
                "prompt": self._llm_prompt.toPlainText(),
                "timeout": self._llm_timeout.value(),
                "max_retries": self._llm_retries.value(),
                "max_tokens": self._llm_max_tokens.value(),
                "image_max_side": self._llm_image_side.value(),
                "threads": self._llm_threads.value(),
            },
            "processing": {
                "skip_existing": self._proc_skip.isChecked(),
                "batch_size": self._proc_batch.value(),
                "max_workers": self._proc_workers.value(),
            },
        }

    def _set_status(self, text: str, error: bool = False):
        """Update the status label with appropriate colour."""
        colour = "#f38ba8" if error else "#a6e3a1"  # Catppuccin red / green
        self._status.setStyleSheet(f"font-size: 11px; color: {colour};")
        self._status.setText(text)

    def _save(self):
        """Collect widget values and write them to config.local.yaml."""
        data = self._collect()
        with open(CONFIG_LOCAL, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True,
                      sort_keys=False)
        self._set_status(f"Saved to {CONFIG_LOCAL}")

    def _save_and_accept(self):
        """Save settings and close the dialog with accept."""
        self._save()
        self.accept()

    def get_collected(self) -> dict:
        """Return the last collected values (call after exec())."""
        return self._collect()
