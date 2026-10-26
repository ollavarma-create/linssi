"""SQLite database — read-only viewer for Linssi image metadata."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timedelta


class Database:
    """Read-only image metadata database backed by SQLite."""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self._cache: dict = {}
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

    @contextmanager
    def _conn(self):
        """Context manager that opens a read-only SQLite connection."""
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only = ON")
        try:
            yield conn
        finally:
            conn.close()

    def get_secondary_dirs(self) -> list[str]:
        """Return all secondary image directory paths stored in the database."""
        try:
            with self._conn() as conn:
                return [r[0] for r in conn.execute(
                    "SELECT dir_path FROM secondary_dirs ORDER BY dir_path"
                ).fetchall()]
        except Exception:
            return []

    def get_images(self, query: str = "",
                   query_and: list | None = None,
                   query_or: list | None = None,
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
        terms_or = query_or or []

        if not terms_and and not terms_or and query:
            terms_and = [query]

        for term in terms_and:
            ex, ep = self._term_exists(term)
            conditions.append(ex)
            params.extend(ep)

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

    @staticmethod
    def _term_exists(term: str) -> tuple[str, list]:
        """Build an EXISTS subquery fragment that checks all text fields for a single term."""
        p = f"%{term}%"
        sql = """EXISTS (
            SELECT 1
            FROM images i2
            LEFT JOIN exif_data e2        ON i2.id = e2.image_id
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
        try:
            with self._conn() as conn:
                return [r[0] for r in conn.execute(
                    "SELECT DISTINCT class_name FROM yolo_detections"
                    " WHERE class_name IS NOT NULL ORDER BY class_name"
                ).fetchall()]
        except Exception:
            return []

    def get_distinct_cameras(self) -> list[str]:
        """Return all distinct camera makes, models, and combined strings, sorted."""
        try:
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
        except Exception:
            return []

    def get_distinct_persons(self) -> list[str]:
        """Return all identified person names (excluding 'unknown'), sorted alphabetically."""
        try:
            with self._conn() as conn:
                return [r[0] for r in conn.execute(
                    "SELECT DISTINCT person_name FROM face_detections"
                    " WHERE person_name IS NOT NULL AND person_name != 'unknown'"
                    " ORDER BY person_name"
                ).fetchall()]
        except Exception:
            return []

    def get_date_range(self) -> tuple[str, str]:
        """Return (oldest, newest) date_taken strings, or ('', '') if none."""
        try:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT MIN(date_taken), MAX(date_taken) FROM exif_data WHERE date_taken IS NOT NULL"
                ).fetchone()
                return (row[0] or "", row[1] or "")
        except Exception:
            return ("", "")

    def stats(self) -> dict:
        """Return total image count and per-stage completion counts."""
        try:
            with self._conn() as conn:
                total = conn.execute("SELECT COUNT(*) as n FROM images").fetchone()["n"]
                stages = {}
                for stage in ["exif", "yolo", "faces", "llm"]:
                    try:
                        done = conn.execute(
                            "SELECT COUNT(*) as n FROM processing_log WHERE stage = ? AND status = 'done'",
                            (stage,),
                        ).fetchone()["n"]
                        stages[stage] = done
                    except Exception:
                        stages[stage] = 0
                return {"total_images": total, "completed": stages}
        except Exception:
            return {"total_images": 0, "completed": {}}

    def db_size(self) -> int:
        """Return the current database file size in bytes."""
        return self.db_path.stat().st_size if self.db_path.exists() else 0

    def get_top_cameras(self, limit: int = 5) -> list[tuple[str, int]]:
        """Return the most frequent camera names and their image counts, cached."""
        cache_key = f"top_cameras_{limit}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        try:
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
        except Exception:
            return []

    def get_top_objects(self, limit: int = 5) -> list[tuple[str, int]]:
        """Return the most frequent YOLO object classes and their detection counts, cached."""
        cache_key = f"top_objects_{limit}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        try:
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
        except Exception:
            return []

    def get_top_persons(self, limit: int = 5) -> list[tuple[str, int]]:
        """Return the most frequently identified persons (excluding 'unknown') and their counts, cached."""
        cache_key = f"top_persons_{limit}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        try:
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
        except Exception:
            return []

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
        except Exception:
            return []
