"""SQLite database for image metadata storage."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timedelta


class Database:
    """Image metadata database backed by SQLite."""

    def __init__(self, db_path: str = "data/image_analyzer.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
        self._cache = {}
        self._cache_ttl = 300  # 5 minutes

    def _cache_get(self, key):
        """Return a cached value by key if still within TTL, otherwise None."""
        if key in self._cache:
            timestamp, value = self._cache[key]
            if datetime.now() - timestamp < timedelta(seconds=self._cache_ttl):
                return value
        return None

    def _cache_set(self, key, value):
        """Store a value in the in-memory cache with the current timestamp."""
        self._cache[key] = (datetime.now(), value)

    def _init_schema(self):
        """Create all tables and indexes if they do not yet exist, and run one-time migrations."""
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT UNIQUE NOT NULL,
                    file_hash TEXT,
                    file_size INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS exif_data (
                    image_id INTEGER PRIMARY KEY REFERENCES images(id),
                    camera_make TEXT, camera_model TEXT, date_taken TEXT,
                    gps_lat REAL, gps_lon REAL, focal_length REAL,
                    aperture REAL, iso INTEGER, exposure_time TEXT,
                    width INTEGER, height INTEGER, orientation INTEGER,
                    raw_json TEXT
                );
                CREATE TABLE IF NOT EXISTS yolo_detections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    image_id INTEGER REFERENCES images(id),
                    class_name TEXT NOT NULL, confidence REAL,
                    bbox_x1 REAL, bbox_y1 REAL, bbox_x2 REAL, bbox_y2 REAL
                );
                CREATE TABLE IF NOT EXISTS face_detections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    image_id INTEGER REFERENCES images(id),
                    person_name TEXT, confidence REAL,
                    bbox_x1 REAL, bbox_y1 REAL, bbox_x2 REAL, bbox_y2 REAL,
                    embedding BLOB
                );
                CREATE TABLE IF NOT EXISTS llm_descriptions (
                    image_id INTEGER PRIMARY KEY REFERENCES images(id),
                    description TEXT, model_used TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS processing_log (
                    image_id INTEGER REFERENCES images(id),
                    stage TEXT NOT NULL, status TEXT NOT NULL,
                    error_message TEXT,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (image_id, stage)
                );
                CREATE INDEX IF NOT EXISTS idx_yolo_class ON yolo_detections(class_name);
                CREATE INDEX IF NOT EXISTS idx_face_person ON face_detections(person_name);
                CREATE INDEX IF NOT EXISTS idx_images_file_path ON images(file_path);
                CREATE INDEX IF NOT EXISTS idx_exif_date ON exif_data(date_taken);
                CREATE INDEX IF NOT EXISTS idx_processing_log_status ON processing_log(stage, status);
                CREATE INDEX IF NOT EXISTS idx_exif_camera ON exif_data(camera_make, camera_model);              
                CREATE INDEX IF NOT EXISTS idx_exif_gps ON exif_data(gps_lat, gps_lon);
                CREATE TABLE IF NOT EXISTS secondary_dirs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dir_path TEXT UNIQUE NOT NULL,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            # One-time migration: normalize EXIF dates from YYYY:MM:DD to YYYY-MM-DD
            conn.execute("""
                UPDATE exif_data
                SET date_taken = substr(date_taken,1,4)||'-'||substr(date_taken,6,2)||'-'||substr(date_taken,9)
                WHERE date_taken LIKE '____:__:%'
            """)


    @contextmanager
    def _conn(self):
        """Context manager that opens a SQLite connection, commits on success, rolls back on error."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def delete_image_by_id(self, image_id: int) -> str:
        """Delete image and all related data. Returns file_path for disk deletion."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT file_path FROM images WHERE id = ?", (image_id,)
            ).fetchone()
            if not row:
                return ""
            file_path = row["file_path"]
            for table in ("yolo_detections", "face_detections", "exif_data",
                          "llm_descriptions", "processing_log"):
                conn.execute(f"DELETE FROM {table} WHERE image_id = ?", (image_id,))
            conn.execute("DELETE FROM images WHERE id = ?", (image_id,))
            return file_path

    def get_secondary_dirs(self) -> list[str]:
        """Return all secondary image directory paths stored in the database."""
        with self._conn() as conn:
            return [r[0] for r in conn.execute(
                "SELECT dir_path FROM secondary_dirs ORDER BY dir_path"
            ).fetchall()]

    def add_secondary_dir(self, dir_path: str):
        """Add a secondary image directory path, ignoring duplicates."""
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO secondary_dirs (dir_path) VALUES (?)", (dir_path,)
            )

    def remove_secondary_dir(self, dir_path: str):
        """Remove a secondary image directory path from the database."""
        with self._conn() as conn:
            conn.execute(
                "DELETE FROM secondary_dirs WHERE dir_path = ?", (dir_path,)
            )

    def add_image(self, file_path: str, file_hash: str = "", file_size: int = 0) -> int:
        """Insert a new image row or return its existing id if already registered."""
        with self._conn() as conn:
            row = conn.execute("SELECT id FROM images WHERE file_path = ?", (file_path,)).fetchone()
            if row:
                return row["id"]
            cur = conn.execute(
                "INSERT INTO images (file_path, file_hash, file_size) VALUES (?, ?, ?)",
                (file_path, file_hash, file_size),
            )
            return cur.lastrowid

    def save_exif(self, image_id: int, exif: dict):
        """Upsert EXIF metadata for the given image."""
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO exif_data
                   (image_id, camera_make, camera_model, date_taken, gps_lat, gps_lon,
                    focal_length, aperture, iso, exposure_time, width, height, orientation, raw_json)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (image_id, exif.get("make"), exif.get("model"), exif.get("date_taken"),
                 exif.get("gps_lat"), exif.get("gps_lon"), exif.get("focal_length"),
                 exif.get("aperture"), exif.get("iso"), exif.get("exposure_time"),
                 exif.get("width"), exif.get("height"), exif.get("orientation"),
                 json.dumps(exif.get("raw", {}))),
            )

    def save_yolo_detections(self, image_id: int, detections: list[dict]):
        """Replace all YOLO detections for the given image with the new list."""
        with self._conn() as conn:
            conn.execute("DELETE FROM yolo_detections WHERE image_id = ?", (image_id,))
            conn.executemany(
                """INSERT INTO yolo_detections
                   (image_id, class_name, confidence, bbox_x1, bbox_y1, bbox_x2, bbox_y2)
                   VALUES (?,?,?,?,?,?,?)""",
                [(image_id, d["class_name"], d["confidence"],
                  d["bbox"][0], d["bbox"][1], d["bbox"][2], d["bbox"][3]) for d in detections],
            )

    def save_face_detections(self, image_id: int, faces: list[dict]):
        """Replace all face detections for the given image with the new list."""
        with self._conn() as conn:
            conn.execute("DELETE FROM face_detections WHERE image_id = ?", (image_id,))
            conn.executemany(
                """INSERT INTO face_detections
                   (image_id, person_name, confidence, bbox_x1, bbox_y1, bbox_x2, bbox_y2)
                   VALUES (?,?,?,?,?,?,?)""",
                [(image_id, f.get("person_name", "unknown"), f.get("confidence", 0.0),
                  f["bbox"][0], f["bbox"][1], f["bbox"][2], f["bbox"][3]) for f in faces],
            )

    def save_llm_description(self, image_id: int, description: str, model: str):
        """Upsert an LLM-generated description for the given image."""
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO llm_descriptions (image_id, description, model_used) VALUES (?,?,?)",
                (image_id, description, model),
            )

    def mark_stage(self, image_id: int, stage: str, status: str, error: str = ""):
        """Record the processing status ('done' or 'error') of a pipeline stage for an image."""
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO processing_log (image_id, stage, status, error_message) VALUES (?,?,?,?)",
                (image_id, stage, status, error),
            )

    def is_stage_done(self, image_id: int, stage: str) -> bool:
        """Return True if the given pipeline stage completed successfully for this image."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT status FROM processing_log WHERE image_id = ? AND stage = ?",
                (image_id, stage),
            ).fetchone()
            return row is not None and row["status"] == "done"

    def get_all_images(self, limit: int = 0) -> list[dict]:
        """Return all image rows, optionally capped to the given limit (0 = no limit)."""
        with self._conn() as conn:
            q = "SELECT * FROM images"
            if limit > 0:
                q += f" LIMIT {limit}"
            return [dict(r) for r in conn.execute(q).fetchall()]

    def get_unprocessed(self, stage: str, limit: int = 0) -> list[dict]:
        """Return images that have not yet been successfully processed by the given stage."""
        with self._conn() as conn:
            q = """SELECT i.* FROM images i
                   LEFT JOIN processing_log p ON i.id = p.image_id AND p.stage = ?
                   WHERE p.status IS NULL OR p.status != 'done'"""
            if limit > 0:
                q += f" LIMIT {limit}"
            return [dict(r) for r in conn.execute(q, (stage,)).fetchall()]

    def search(self, query: str) -> list[dict]:
        """Search all text fields (path, camera, description, objects, persons) with a single term."""
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(
                """SELECT DISTINCT i.file_path,
                          e.date_taken, e.camera_model, e.gps_lat, e.gps_lon,
                          l.description,
                          GROUP_CONCAT(DISTINCT y.class_name) as objects,
                          GROUP_CONCAT(DISTINCT f.person_name) as persons
                   FROM images i
                   LEFT JOIN exif_data e ON i.id = e.image_id
                   LEFT JOIN llm_descriptions l ON i.id = l.image_id
                   LEFT JOIN yolo_detections y ON i.id = y.image_id
                   LEFT JOIN face_detections f ON i.id = f.image_id
                   WHERE i.file_path LIKE ?
                      OR e.camera_model LIKE ?
                      OR l.description LIKE ?
                      OR y.class_name LIKE ?
                      OR f.person_name LIKE ?
                   GROUP BY i.id""",
                (f"%{query}%",) * 5,
            ).fetchall()]

    @staticmethod
    def _term_exists(term: str) -> tuple[str, list]:
        """Build an EXISTS subquery fragment that checks all text fields for a single term."""
        p = f"%{term}%"
        sql = """EXISTS (
            SELECT 1
            FROM images i2
            LEFT JOIN exif_data e2      ON i2.id = e2.image_id
            LEFT JOIN llm_descriptions l2 ON i2.id = l2.image_id
            LEFT JOIN yolo_detections y2  ON i2.id = y2.image_id
            LEFT JOIN face_detections f2  ON i2.id = f2.image_id
            WHERE i2.id = i.id
              AND (i2.file_path LIKE ?
                   OR e2.camera_model LIKE ?
                   OR l2.description  LIKE ?
                   OR y2.class_name   LIKE ?
                   OR f2.person_name  LIKE ?)
        )"""
        return sql, [p, p, p, p, p]

    def get_images(self, query: str = "",
                   query_and: list | None = None,
                   query_or:  list | None = None,
                   query_mode: str = "and",
                   date_from: str = "", date_to: str = "",
                   camera: str = "", obj: str = "", person: str = "",
                   limit: int = 50) -> list[dict]:
        """Return a filtered image list for the thumbnail grid.

        Args:
            query: Legacy single-term fallback when query_and/query_or are absent.
            query_and: All terms must match the image (AND / & syntax).
            query_or: Any one term is sufficient (OR / , syntax).
            query_mode: Ignored — kept for backwards compatibility.
            date_from: Lower bound on date_taken (YYYY-MM-DD).
            date_to: Upper bound on date_taken (YYYY-MM-DD).
            camera: Partial match against camera_make or camera_model.
            obj: Partial match against YOLO class_name (LIKE %term%).
            person: Exact match against face person_name.
            limit: Maximum rows to return (0 = no limit).
        """
        conditions: list[str] = []
        params: list = []

        terms_and = query_and or []
        terms_or  = query_or  or []

        # Fallback vanhoille kutsuille joilla ei ole query_and/query_or
        if not terms_and and not terms_or and query:
            terms_and = [query]

        # AND: jokainen termi lisätään omana EXISTS-ehtona
        for term in terms_and:
            ex, ep = self._term_exists(term)
            conditions.append(ex)
            params.extend(ep)

        # OR: termit yhdistetään yhteen EXISTS-ehtoon OR-operaattorilla
        if terms_or:
            or_parts = []
            for term in terms_or:
                ex, ep = self._term_exists(term)
                or_parts.append(ex)
                params.extend(ep)
            conditions.append("(" + " OR ".join(or_parts) + ")")

        if date_from:
            conditions.append("DATE(e.date_taken) >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("DATE(e.date_taken) <= ?")
            params.append(date_to)
        if camera:
            conditions.append("(e.camera_make LIKE ? OR e.camera_model LIKE ?)")
            params.extend([f"%{camera}%", f"%{camera}%"])
        if obj:
            conditions.append("y.class_name LIKE ?")
            params.append(f"%{obj}%")
        if person:
            conditions.append("f.person_name = ?")
            params.append(person)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        q = f"""SELECT i.id, i.file_path,
                       e.date_taken, e.camera_model,
                       GROUP_CONCAT(DISTINCT y.class_name) as objects,
                       GROUP_CONCAT(DISTINCT f.person_name) as persons
                FROM images i
                LEFT JOIN exif_data e        ON i.id = e.image_id
                LEFT JOIN llm_descriptions l  ON i.id = l.image_id
                LEFT JOIN yolo_detections y   ON i.id = y.image_id
                LEFT JOIN face_detections f   ON i.id = f.image_id
                {where}
                GROUP BY i.id
                ORDER BY e.date_taken DESC NULLS LAST"""
        if limit > 0:
            q += f" LIMIT {limit}"
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(q, params).fetchall()]

    def get_image_detail(self, image_id: int) -> dict:
        """Full metadata for a single image (all tables joined)."""
        with self._conn() as conn:
            row = conn.execute(
                """SELECT i.file_path, i.file_size,
                          e.camera_make, e.camera_model, e.date_taken,
                          e.gps_lat, e.gps_lon, e.focal_length, e.aperture,
                          e.iso, e.exposure_time, e.width, e.height, e.orientation,
                          l.description
                   FROM images i
                   LEFT JOIN exif_data e ON i.id = e.image_id
                   LEFT JOIN llm_descriptions l ON i.id = l.image_id
                   WHERE i.id = ?""",
                (image_id,),
            ).fetchone()
            if not row:
                return {}
            result = dict(row)

            # Resolve path against secondary dirs if primary is missing
            primary = result.get("file_path", "")
            if primary and not Path(primary).exists():
                filename = Path(primary).name
                for sec_dir in self.get_secondary_dirs():
                    candidate = Path(sec_dir) / filename
                    if candidate.exists():
                        result["file_path"] = str(candidate)
                        break

            result["objects"] = [
                dict(r) for r in conn.execute(
                    """SELECT class_name, confidence, bbox_x1, bbox_y1, bbox_x2, bbox_y2
                       FROM yolo_detections WHERE image_id = ? ORDER BY confidence DESC""",
                    (image_id,),
                ).fetchall()
            ]
            result["persons"] = [
                dict(r) for r in conn.execute(
                    """SELECT person_name, confidence, bbox_x1, bbox_y1, bbox_x2, bbox_y2
                       FROM face_detections WHERE image_id = ? ORDER BY confidence DESC""",
                    (image_id,),
                ).fetchall()
            ]
            return result

    def get_distinct_objects(self) -> list[str]:
        """Return all distinct YOLO class names found in the database, sorted alphabetically."""
        with self._conn() as conn:
            return [r[0] for r in conn.execute(
                "SELECT DISTINCT class_name FROM yolo_detections"
                " WHERE class_name IS NOT NULL ORDER BY class_name"
            ).fetchall()]

    def get_distinct_cameras(self) -> list[str]:
        """Return all distinct camera makes, models, and combined strings, sorted."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT camera_make, camera_model FROM exif_data"
                " WHERE camera_make IS NOT NULL OR camera_model IS NOT NULL"
            ).fetchall()
        result: set[str] = set()
        for make, model in rows:
            if make:
                result.add(make.strip())
            if model:
                result.add(model.strip())
            if make and model:
                result.add(f"{make.strip()} {model.strip()}")
        return sorted(result)

    def get_distinct_persons(self) -> list[str]:
        """Return all identified person names (excluding 'unknown'), sorted alphabetically."""
        with self._conn() as conn:
            return [r[0] for r in conn.execute(
                "SELECT DISTINCT person_name FROM face_detections"
                " WHERE person_name IS NOT NULL AND person_name != 'unknown'"
                " ORDER BY person_name"
            ).fetchall()]

    def get_date_range(self) -> tuple[str, str]:
        """Return (oldest, newest) date_taken strings, or ('', '') if none."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT MIN(date_taken), MAX(date_taken) FROM exif_data WHERE date_taken IS NOT NULL"
            ).fetchone()
            return (row[0] or "", row[1] or "")

    def stats(self) -> dict:
        """Return total image count and per-stage completion counts."""
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) as n FROM images").fetchone()["n"]
            stages = {}
            for stage in ["exif", "yolo", "faces", "llm"]:
                done = conn.execute(
                    "SELECT COUNT(*) as n FROM processing_log WHERE stage = ? AND status = 'done'",
                    (stage,),
                ).fetchone()["n"]
                stages[stage] = done
            return {"total_images": total, "completed": stages}

    def db_size(self) -> int:
        """Return the current database file size in bytes."""
        with self._conn() as conn:
            page_count = conn.execute("PRAGMA page_count").fetchone()[0]
            page_size = conn.execute("PRAGMA page_size").fetchone()[0]
            return page_count * page_size

    def get_top_cameras(self, limit: int = 5) -> list[tuple[str, int]]:
        """Return the most frequent camera names and their image counts, cached."""
        cache_key = f"top_cameras_{limit}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        with self._conn() as conn:
            result = [
                (row[0], row[1]) for row in conn.execute("""
                    SELECT 
                        CASE 
                            WHEN camera_make IS NOT NULL AND camera_model IS NOT NULL 
                            THEN camera_make || ' ' || camera_model
                            WHEN camera_make IS NOT NULL THEN camera_make
                            WHEN camera_model IS NOT NULL THEN camera_model
                            ELSE 'Unknown'
                        END as camera,
                        COUNT(*) as count
                    FROM exif_data 
                    WHERE camera_make IS NOT NULL OR camera_model IS NOT NULL
                    GROUP BY camera
                    ORDER BY count DESC
                    LIMIT ?
                """, (limit,)).fetchall()
            ]
            self._cache_set(cache_key, result)
            return result

    def get_top_objects(self, limit: int = 5) -> list[tuple[str, int]]:
        """Return the most frequent YOLO object classes and their detection counts, cached."""
        cache_key = f"top_objects_{limit}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        with self._conn() as conn:
            result = [
                (row[0], row[1]) for row in conn.execute("""
                    SELECT class_name, COUNT(*) as count
                    FROM yolo_detections
                    GROUP BY class_name
                    ORDER BY count DESC
                    LIMIT ?
                """, (limit,)).fetchall()
            ]
            self._cache_set(cache_key, result)
            return result

    def get_top_persons(self, limit: int = 5) -> list[tuple[str, int]]:
        """Return the most frequently identified persons (excluding 'unknown') and their counts, cached."""
        cache_key = f"top_persons_{limit}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        with self._conn() as conn:
            result = [
                (row[0], row[1]) for row in conn.execute("""
                    SELECT person_name, COUNT(*) as count
                    FROM face_detections
                    WHERE person_name != 'unknown' AND person_name IS NOT NULL
                    GROUP BY person_name
                    ORDER BY count DESC
                    LIMIT ?
                """, (limit,)).fetchall()
            ]
            self._cache_set(cache_key, result)
            return result

    def get_file_paths_by_prefix(self, dir_path: str) -> list[str]:
        """Return file paths of all images whose path starts with dir_path."""
        with self._conn() as conn:
            return [r[0] for r in conn.execute(
                "SELECT file_path FROM images WHERE file_path LIKE ? ORDER BY file_path",
                (f"{dir_path}%",),
            ).fetchall()]

    def delete_images_by_path_prefix(self, dir_path: str) -> int:
        """Delete all images whose file_path starts with dir_path and all related data.

        Returns the number of deleted image rows.
        """
        pattern = f"{dir_path}%"
        with self._conn() as conn:
            ids = [r[0] for r in conn.execute(
                "SELECT id FROM images WHERE file_path LIKE ?", (pattern,)
            ).fetchall()]
            if not ids:
                return 0
            placeholders = ",".join("?" * len(ids))
            for table in ("yolo_detections", "face_detections", "exif_data",
                          "llm_descriptions", "processing_log"):
                conn.execute(
                    f"DELETE FROM {table} WHERE image_id IN ({placeholders})", ids
                )
            conn.execute(
                f"DELETE FROM images WHERE id IN ({placeholders})", ids
            )
            return len(ids)

    def get_top_locations(self, limit: int = 5) -> list[tuple[str, int]]:
        """Return the most common GPS locations (rounded to 2 decimal places) and their counts, cached."""
        cache_key = f"top_locations_{limit}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        try:
            with self._conn() as conn:
                result = [
                    (f"{lat:.2f}, {lon:.2f}", count) for lat, lon, count in conn.execute("""
                        SELECT ROUND(gps_lat, 2) as lat, ROUND(gps_lon, 2) as lon, COUNT(*) as count
                        FROM exif_data
                        WHERE gps_lat IS NOT NULL AND gps_lon IS NOT NULL
                        GROUP BY lat, lon
                        ORDER BY count DESC
                        LIMIT ?
                    """, (limit,)).fetchall()
                ]
                self._cache_set(cache_key, result)
                return result
        except Exception as e:
            print(f"Error fetching top locations: {e}")
            return []

