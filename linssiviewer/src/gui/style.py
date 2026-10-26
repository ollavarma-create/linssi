"""Dark mode stylesheet (Catppuccin Mocha palette) for Linssi GUI."""


def dark_stylesheet() -> str:
    """Return QSS string for full dark mode styling."""
    # Catppuccin Mocha palette
    BG_BASE = "#1e1e2e"
    BG_MANTLE = "#181825"
    BG_SURFACE0 = "#313244"
    BG_SURFACE1 = "#45475a"
    BG_SURFACE2 = "#585b70"
    BORDER = "#45475a"
    ACCENT = "#89b4fa"
    ACCENT_HOV = "#b4befe"
    TEXT = "#cdd6f4"
    SUBTEXT = "#a6adc8"
    MUTED = "#6c7086"
    SUCCESS = "#a6e3a1"  # noqa: F841 — available for future use
    ERROR = "#f38ba8"  # noqa: F841 — available for future use

    return f"""
/* ── Base ── */
QMainWindow, QWidget {{
    background-color: {BG_BASE};
    color: {TEXT};
    font-family: "Segoe UI", "Liberation Sans", sans-serif;
    font-size: 13px;
}}

QDialog {{
    background-color: {BG_BASE};
    color: {TEXT};
}}

/* ── Splitter ── */
QSplitter::handle:horizontal {{
    background-color: {BORDER};
    width: 1px;
}}

/* ── Scroll areas / panels ── */
QScrollArea, QAbstractScrollArea {{
    background-color: {BG_MANTLE};
    border: none;
}}

/* ── Labels ── */
QLabel {{
    color: {TEXT};
    background-color: transparent;
}}

/* ── HLine frame separator ── */
QFrame[frameShape="4"] {{
    color: {BORDER};
    border: none;
    border-top: 1px solid {BORDER};
}}

/* ── List / thumbnail grid ── */
QListWidget {{
    background-color: {BG_SURFACE0};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    outline: none;
}}
QListWidget::item {{
    border-radius: 2px;
    padding: 2px;
}}
QListWidget::item:hover {{
    background-color: {BG_SURFACE1};
}}
QListWidget::item:selected {{
    background-color: {BG_SURFACE2};
    border-left: 3px solid {ACCENT};
    color: {TEXT};
}}

/* ── Tree widget ── */
QTreeWidget {{
    background-color: {BG_SURFACE0};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    outline: none;
}}
QTreeWidget::item:hover {{
    background-color: {BG_SURFACE1};
}}
QTreeWidget::item:selected {{
    background-color: {BG_SURFACE2};
    color: {TEXT};
}}

QHeaderView::section {{
    background-color: {BG_SURFACE1};
    color: {SUBTEXT};
    border: none;
    border-right: 1px solid {BORDER};
    padding: 4px 6px;
}}

/* ── Buttons ── */
QPushButton {{
    background-color: {BG_SURFACE0};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 5px 12px;
    min-height: 22px;
}}
QPushButton:hover {{
    background-color: {BG_SURFACE1};
    border-color: {ACCENT};
}}
QPushButton:pressed {{
    background-color: {BG_SURFACE2};
}}
QPushButton:disabled {{
    color: {MUTED};
    border-color: {BG_SURFACE1};
}}

/* ── Line edits ── */
QLineEdit {{
    background-color: {BG_SURFACE0};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px 6px;
    selection-background-color: {ACCENT};
    selection-color: {BG_BASE};
}}
QLineEdit:focus {{
    border-color: {ACCENT};
}}
QLineEdit::placeholder {{
    color: {MUTED};
}}

/* ── Text edit ── */
QTextEdit {{
    background-color: {BG_SURFACE0};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px;
    selection-background-color: {ACCENT};
    selection-color: {BG_BASE};
}}
QTextEdit:focus {{
    border-color: {ACCENT};
}}

/* ── Combo box ── */
QComboBox {{
    background-color: {BG_SURFACE0};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px 6px;
    min-height: 22px;
}}
QComboBox:hover {{
    border-color: {ACCENT};
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {SUBTEXT};
    width: 0;
    height: 0;
    margin-right: 4px;
}}
QComboBox QAbstractItemView {{
    background-color: {BG_SURFACE0};
    color: {TEXT};
    border: 1px solid {ACCENT};
    selection-background-color: {BG_SURFACE2};
    selection-color: {TEXT};
    outline: none;
}}

/* ── Spin boxes ── */
QSpinBox, QDoubleSpinBox {{
    background-color: {BG_SURFACE0};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px 6px;
}}
QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {ACCENT};
}}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    background-color: {BG_SURFACE1};
    border: none;
    width: 16px;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
    background-color: {BG_SURFACE2};
}}

/* ── Check boxes ── */
QCheckBox {{
    color: {TEXT};
    spacing: 6px;
}}
QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {BORDER};
    border-radius: 3px;
    background-color: {BG_SURFACE0};
}}
QCheckBox::indicator:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
}}
QCheckBox::indicator:hover {{
    border-color: {ACCENT_HOV};
}}

/* ── Tab widget (settings dialog) ── */
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 4px;
    background-color: {BG_BASE};
}}
QTabBar::tab {{
    background-color: {BG_MANTLE};
    color: {SUBTEXT};
    border: 1px solid {BORDER};
    border-bottom: none;
    border-radius: 4px 4px 0 0;
    padding: 6px 14px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background-color: {BG_SURFACE0};
    color: {TEXT};
    border-bottom: 2px solid {ACCENT};
}}
QTabBar::tab:hover:!selected {{
    background-color: {BG_SURFACE1};
    color: {TEXT};
}}

/* ── Scroll bars ── */
QScrollBar:vertical {{
    background-color: {BG_MANTLE};
    width: 10px;
    border: none;
}}
QScrollBar::handle:vertical {{
    background-color: {BG_SURFACE2};
    border-radius: 5px;
    min-height: 24px;
    margin: 2px;
}}
QScrollBar::handle:vertical:hover {{
    background-color: {ACCENT};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
    background: none;
}}
QScrollBar:horizontal {{
    background-color: {BG_MANTLE};
    height: 10px;
    border: none;
}}
QScrollBar::handle:horizontal {{
    background-color: {BG_SURFACE2};
    border-radius: 5px;
    min-width: 24px;
    margin: 2px;
}}
QScrollBar::handle:horizontal:hover {{
    background-color: {ACCENT};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
    background: none;
}}

/* ── Completer popup ── */
QListView {{
    background-color: {BG_SURFACE0};
    color: {TEXT};
    border: 1px solid {ACCENT};
    selection-background-color: {BG_SURFACE2};
    selection-color: {TEXT};
    outline: none;
}}

/* ── Tooltip ── */
QToolTip {{
    background-color: {BG_SURFACE1};
    color: {TEXT};
    border: 1px solid {ACCENT};
    border-radius: 3px;
    padding: 4px 6px;
}}
"""
