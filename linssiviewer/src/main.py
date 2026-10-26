"""Entry point for Linssi Viewer."""

import argparse
import logging
import sys


def main():
    """Parse CLI arguments and launch the GUI."""
    parser = argparse.ArgumentParser(description="Linssi Viewer — read-only photo browser")
    parser.add_argument("--db", metavar="PATH", help="Path to Linssi SQLite database")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    from PySide6.QtWidgets import QApplication, QFileDialog
    from src.gui.main_window import MainWindow
    from src.gui.style import dark_stylesheet

    app = QApplication(sys.argv)
    app.setStyleSheet(dark_stylesheet())

    db_path = args.db or ""

    if not db_path:
        db_path, _ = QFileDialog.getOpenFileName(
            None,
            "Open Linssi database",
            "",
            "SQLite databases (*.db *.sqlite *.sqlite3);;All files (*)",
        )
        if not db_path:
            sys.exit(0)

    from src.database import Database
    from src.config import AppConfig

    db = Database(db_path)
    config = AppConfig(database_path=db_path)

    window = MainWindow(db, config)
    window.resize(1280, 800)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
