"""CLI entry point for Linssi image analysis pipeline."""
import argparse
import logging
import sys

from tqdm import tqdm

from src.config import load_config
from src.database import Database
from src.pipeline.scanner import scan_images
from src.pipeline.exif_reader import ExifReader
from src.pipeline.yolo_detector import YoloDetector
from src.pipeline.face_recognizer import FaceRecognizer
from src.pipeline.llm_describer import LLMDescriber


def main():
    """Parse CLI arguments and dispatch to the requested mode (GUI, stage, search, or stats)."""
    parser = argparse.ArgumentParser(description="Linssi – locally running imageanalyzer")
    parser.add_argument("--config", help="Path to the config file")
    parser.add_argument("--stage", choices=["scan", "exif", "yolo", "faces", "llm"],
                        help="Execute stage")
    parser.add_argument("--search", metavar="search item", help="Search from indexed images")
    parser.add_argument("--stats", action="store_true", help="Show processed status")
    parser.add_argument("--limit", type=int, default=0, metavar="N",
                        help="Limit images to be processed")
    parser.add_argument("--force", action="store_true",
                        help="Re-process all images, even already-done ones")
    parser.add_argument("--gui", action="store_true", help="Open graphical interface")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    config = load_config(args.config)
    db = Database(config.database_path)

    if args.gui:
        from PyQt6.QtWidgets import QApplication
        from src.gui.main_window import MainWindow
        from src.gui.style import dark_stylesheet
        app = QApplication(sys.argv)
        app.setStyleSheet(dark_stylesheet())
        window = MainWindow(db, config)
        window.resize(1280, 800)
        window.show()
        sys.exit(app.exec())

    if args.stage:
        _run_stage(args, config, db)
    elif args.search:
        _run_search(args.search, db)
    elif args.stats:
        _run_stats(db)
    else:
        parser.print_help()
        sys.exit(1)


def _run_stage(args, config, db):
    """Scan for new images and run the requested pipeline stage with progress reporting."""
    # Always scan first to register new images
    images = scan_images(config, db)

    if args.stage == "scan":
        print(f"Scanned {len(images)} images.")
        return

    # Get images to process — all if --force, otherwise only unprocessed
    if args.force:
        pending = db.get_all_images(args.limit)
    else:
        pending = db.get_unprocessed(args.stage, args.limit)
    if not pending:
        print(f"All images are already processed '{args.stage}'.")
        return

    if args.stage == "exif":
        stage = ExifReader(db)
    elif args.stage == "yolo":
        stage = YoloDetector(db, config.yolo)
    elif args.stage == "faces":
        stage = FaceRecognizer(db, config.faces)
    elif args.stage == "llm":
        stage = LLMDescriber(db, config.llm)

    ok = err = 0
    force = args.force
    if args.stage == "llm":
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=config.llm.threads) as pool:
            futures = {pool.submit(stage.run, row["id"], row["file_path"], force): row for row in pending}
            for future in tqdm(as_completed(futures), total=len(futures), desc="llm", unit="image"):
                if future.result():
                    ok += 1
                else:
                    err += 1
    else:
        for row in tqdm(pending, desc=args.stage, unit="image"):
            if stage.run(row["id"], row["file_path"], force):
                ok += 1
            else:
                err += 1
    print(f"Ready. Processed: {ok}, errors: {err}.")


def _run_search(query: str, db: Database):
    """Print matching images and their metadata to stdout."""
    results = db.search(query)
    if not results:
        print("No search results.")
        return
    for r in results:
        parts = [r["file_path"]]
        if r.get("date_taken"):
            parts.append(r["date_taken"])
        if r.get("camera_model"):
            parts.append(r["camera_model"])
        if r.get("gps_lat") and r.get("gps_lon"):
            parts.append(f"GPS: {r['gps_lat']:.4f}, {r['gps_lon']:.4f}")
        print("  ".join(parts))
        if r.get("description"):
            print(f"  → {r['description'][:120]}")
        if r.get("objects"):
            print(f"  Objects: {r['objects']}")


def _run_stats(db: Database):
    """Print image counts and per-stage completion statistics to stdout."""
    s = db.stats()
    print(f"Total images: {s['total_images']}")
    for stage, count in s["completed"].items():
        print(f"  {stage:8s}: {count} processed")


if __name__ == "__main__":
    main()
